# ELK layout engine

## vis-network graph renderer

`vis-network.min.js` is the unmodified standalone UMD bundle from **vis-network 10.1.2**.
It includes its dependencies and styles and is served locally without a CDN.
License: Apache-2.0 OR MIT; see `vis-network-LICENSE-APACHE-2.0` and `vis-network-LICENSE-MIT`.

Package: https://registry.npmjs.org/vis-network/-/vis-network-10.1.2.tgz
Package integrity (SHA-512): `1Kj7GD7XNjygliqRWXv/VPT1X/2eKz2e09PvwDtETHwuvKJ0emid7/PmWoFqCMypun8rLbjgmalSfPkiVZ8ZMg==`
Documentation: https://visjs.github.io/vis-network/docs/network/

To update, obtain a pinned package, verify its registry integrity, and copy
`standalone/umd/vis-network.min.js` and both license files. Run the graph projection,
fixture browser and live browser tests after updating.

## ELK package

`elk.bundled.js` is the unmodified browser bundle from **elkjs 0.12.0**.
It is served locally so the dashboard works without a CDN or an npm install.
License: EPL-2.0 or GPL-3.0-or-later; see `elk-LICENSE.md`.

Upstream source and build instructions: https://github.com/kieler/elkjs/tree/v0.12.0
Package: https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz
Package integrity (SHA-512): `YZcKynxVxYoKIOEpywEPwCFdg+BTbxQRNf3pbwdDCvc8O3kQD8bmIwSxKU1eOTVc4Xo+VG9Te+575mlfvOrhEQ==`

To update, run `npm pack elkjs@<version> --ignore-scripts` in a scratch directory,
copy `package/lib/elk.bundled.js` and `package/LICENSE.md`, update this notice,
then run `node --test apps/entity-workbench/tests/model-layout.test.mjs` and the modeler browser checks.
