"""Key-free protocol fixture, used only by test_provider_protocol.py."""
import sys
from mcp.server.fastmcp import FastMCP

mcp=FastMCP('edge-contract-fixture')
URL='https://www.tigeretf.com/test-evidence'
TEXT='투자 대상과 자료의 기준일을 공식 문서에서 확인해야 합니다.'
if sys.argv[-1]=='kiwoom':
    @mcp.tool()
    def kiwoom_query(command_path:str,options:dict)->dict:
        if command_path!='domestic stocks info' or options!={'code':'396500','pages':1}: raise ValueError('Unsafe command or scope')
        return {'stk_cd':'396500','stk_nm':'TIGER 반도체TOP10','cur_prc':'12806'}
else:
    @mcp.tool()
    def search(query:str,include_domains:str,page:int,language:str)->dict:
        if not query.startswith('TIGER 반도체TOP10 ') or page!=0 or language!='ko': raise ValueError('Scope changed')
        return {'results':[{'url':URL,'title':'공식 문서 예시'}]}
    @mcp.tool()
    def fetch_content(urls:list[str],format:str,links:bool,image_links:bool,page_metadata:bool,per_url_timeout_ms:int)->dict:
        if urls!=[URL] or format!='markdown' or links or image_links: raise ValueError('Unsafe fetch')
        return {'results':[{'url':URL,'final_url':URL,'title':'공식 문서 예시','text':TEXT}]}

if __name__=='__main__':mcp.run(transport='stdio')
