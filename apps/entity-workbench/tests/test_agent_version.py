import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend import agent_version as versions


class AgentVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.git('init','-q');self.git('config','user.email','test@example.com');self.git('config','user.name','Test')
        self.source=self.root/'apps/entity-workbench/backend/tool.py'
        self.source.parent.mkdir(parents=True);self.source.write_text('value=1\n',encoding='utf8')

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,text=True,stderr=subprocess.DEVNULL).strip()

    def checkpoint(self):
        versions.bump(self.root,'Initial agent');self.git('add','.');self.git('commit','-qm','initial')
        return self.git('rev-parse','HEAD')

    def test_edits_additions_and_deletions_cannot_reuse_registered_sources(self):
        self.checkpoint()
        for content in ['value=2\n',None]:
            if content is None:self.source.unlink()
            else:self.source.write_text(content,encoding='utf8')
            with self.assertRaisesRegex(ValueError,'version'):versions.check(self.root)
            versions.bump(self.root,'Changed tool');versions.check(self.root)
        (self.source.parent/'new_tool.py').write_text('new_tool=1\n',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'version'):versions.check(self.root)

    def test_ci_requires_increase_even_when_checksum_was_refreshed_manually(self):
        base=self.checkpoint();self.source.write_text('value=2\n',encoding='utf8')
        manifest=versions.release(self.root);original=dict(manifest);manifest['source_digest']=versions.source_digest(self.root)
        (self.root/versions.MANIFEST).write_text(json.dumps(manifest),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'increase'):versions.check(self.root,base)
        (self.root/versions.MANIFEST).write_text(json.dumps(original),encoding='utf8')
        versions.bump(self.root,'Correct release');versions.check(self.root,base)

    def test_every_agent_component_is_protected_but_tests_are_not(self):
        for path in ['apps/engine/harness.py','apps/entity-workbench/sql/views/etf.sql',
                     'apps/entity-workbench/ontology/metadata/ETF.yaml','apps/entity-workbench/data/view-design.json',
                     'apps/engine/prompts/system.yaml','.claude/skills/analysis/SKILL.md','tools/score.py']:
            self.assertTrue(versions.protected(path),path)
        self.assertFalse(versions.protected('apps/entity-workbench/tests/test_agent_version.py'))

    def test_published_release_history_cannot_be_rewritten(self):
        base=self.checkpoint();self.source.write_text('value=2',encoding='utf8')
        manifest=versions.bump(self.root,'Tool correction');manifest['history'][0]['summary']='rewritten'
        (self.root/versions.MANIFEST).write_text(json.dumps(manifest),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'history'):versions.check(self.root,base)

    def test_docs_and_line_endings_do_not_create_agent_changes(self):
        base=self.checkpoint();(self.root/'README.md').write_text('Documentation',encoding='utf8')
        self.source.write_bytes(b'value=1\r\n')
        versions.check(self.root,base)

    def test_harness_catalog_and_model_changes_have_distinct_execution_versions(self):
        release=versions.bump(self.root,'Initial agent');harness=self.root/'runtime';harness.mkdir()
        source=harness/'runner.py';source.write_text('run=1',encoding='utf8')
        first=versions.snapshot(release,harness,{'objects':['ETF']},'model-a')
        self.assertEqual(first,versions.snapshot(release,harness,{'objects':['ETF']},'model-a'))
        different_model=versions.snapshot(release,harness,{'objects':['ETF']},'model-b')
        different_catalog=versions.snapshot(release,harness,{'objects':['Company']},'model-a')
        source.write_text('run=2',encoding='utf8')
        different_runtime=versions.snapshot(release,harness,{'objects':['ETF']},'model-a')
        self.assertEqual(len({r['id'] for r in [first,different_model,different_catalog,different_runtime]}),4)


if __name__=='__main__':unittest.main()
