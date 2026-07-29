# References and Attribution

Version 0.2 was designed after reviewing two public Origin automation projects. They informed
tool organization and workflow boundaries only. This repository does not copy their source code,
templates, images, palettes, prompts, or branded assets.

## origin-mcp

- Repository: https://github.com/Ge-Shun/origin-mcp
- Reviewed revision: `fecb7226ed60d7651d921d2586eb9950bf16b618`
- License at the reviewed revision: MIT
- Ideas considered: broad Origin object coverage, structured X-Function access, Origin-native
  analysis operations, FigureSpec-style requests, batch execution, graph previews, templates, and
  local documentation discovery.
- Local implementation: independently written for this plugin's serialized pywin32 COM worker,
  result envelope, ownership gates, source protection, and readback requirements.

## EditaPlot

- Repository: https://github.com/hang-jin/editaplot
- Reviewed revision: `f7151330bda7d82936941a1b9b9aab49ca230eec`
- License at the reviewed revision: Apache-2.0
- Ideas considered: data-first figure planning, explicit scientific semantics, reusable figure
  specifications, palette discipline, artifact bundles, and visual verification.
- Local implementation: independently written as Origin COM, LabTalk, and X-Function operations;
  no EditaPlot code or assets are included.

## OriginLab documentation

The plugin ships short, locally authored capability notes with links to relevant OriginLab pages.
Those links are discoverable with `origin_query_knowledge`. OriginLab documentation is not bundled
or reproduced in this repository.

Origin, OriginPro, LabTalk, and X-Function are products or technologies of OriginLab Corporation.
This project is an independent automation plugin and is not affiliated with or endorsed by
OriginLab.
