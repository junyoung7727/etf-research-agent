# ELK layout engine

`elk.bundled.js` is the unmodified browser bundle from **elkjs 0.12.0**.
It is served locally so the dashboard works without a CDN or an npm install.
License: EPL-2.0 or GPL-3.0-or-later; see `elk-LICENSE.md`.

Upstream source and build instructions: https://github.com/kieler/elkjs/tree/v0.12.0
Package: https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz
Package integrity (SHA-512): `YZcKynxVxYoKIOEpywEPwCFdg+BTbxQRNf3pbwdDCvc8O3kQD8bmIwSxKU1eOTVc4Xo+VG9Te+575mlfvOrhEQ==`

To update, run `npm pack elkjs@<version> --ignore-scripts` in a scratch directory,
copy `package/lib/elk.bundled.js` and `package/LICENSE.md`, update this notice,
then run `node --test apps/entity-workbench/tests/model-layout.test.mjs` and the modeler browser checks.
