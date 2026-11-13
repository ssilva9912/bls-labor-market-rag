# BLS source reuse and attribution

All eight corpus files are unmodified official U.S. Bureau of Labor Statistics
PDF releases. Their exact URLs, dates and hashes are in `corpus/source_inventory.json`.
Source attribution: **U.S. Bureau of Labor Statistics (BLS)**.

[BLS Copyright Information](https://www.bls.gov/opub/copyright-information.htm)
states that its publications are public domain except previously copyrighted
photographs/illustrations and permits use of public-domain material without
specific permission, requesting attribution. Its emblems are separately protected
trademarks. This project does not adopt BLS branding or imply agency endorsement.
Official PDF branding remains part of the original documents. The selected
releases contain BLS statistical text, tables and charts; no credited third-party
photograph or illustration has been selected for reuse as project artwork.

`corpus/provenance/reuse_terms.json` records the official-policy review and its access
method. Direct Python GET of the policy returned403, while official web browsing
successfully displayed it. All eight release PDFs and HTML versions downloaded
successfully with HTTP200. These are source-specific observations, not an
invented Creative Commons license or a blanket claim about state publications.

The former Washington-agency corpus and its obsolete excerpt-bearing artifacts
were removed under the approved manifest. Original question wording and cleanup
hashes remain as non-excerpt provenance; old scores were not reused.
Protected external credentials and local credential helpers were not modified.
Dependencies and Ollama/model weights retain their own licenses and are not
vendored. No license for the author's project code has been chosen on their behalf.
