# Run from the project root in the owner's normal PowerShell session.
# No credentials are read, printed, or embedded by this script.
param([switch]$ResumePublication)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Check-Exit([string]$step) { if ($LASTEXITCODE -ne 0) { throw "$step failed (exit $LASTEXITCODE)." } }
$python=Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create the Python 3.12 environment using README.md first.' }
& $python --version; Check-Exit 'Python access'
if (-not $ResumePublication) {
# Validate in isolation; never replace or uninstall from the working environment.
try {
  & $python -m venv .venv-fresh; Check-Exit 'Create isolated fresh environment'
  $fresh=Join-Path (Get-Location) '.venv-fresh/Scripts/python.exe'
  & $fresh -m pip install -r requirements.txt -r requirements-docs.txt; Check-Exit 'Fresh dependency installation'
  & $fresh -m pip check; Check-Exit 'Fresh dependency compatibility'
  & $fresh -m unittest discover -s tests -v; Check-Exit 'Fresh-environment offline tests'
  Write-Host 'Fresh installation, pip check, and offline tests passed.'
} catch { Write-Warning "Fresh-install validation incomplete: $_. Working environment preserved." }
& $python -m pip check; Check-Exit 'Dependency compatibility'
& $python -m unittest discover -s tests -v; Check-Exit 'Offline tests'
& $python sources.py verify; Check-Exit 'Source verification'
& $python -m scripts.verify_submission --offline; Check-Exit 'Project artifact verification'
& $python -m scripts.verify_submission --offline --package submission; Check-Exit 'Submission verification'
}
# Always rerun focused coverage and publication scanning, including on resume.
& $python -m unittest discover -s tests -p test_publication_audit.py -v; Check-Exit 'Audit regression tests'
if ($ResumePublication) {
  & $python -m scripts.verify_submission --offline --package submission; Check-Exit 'Updated submission verification'
}
& $python -m scripts.publication_audit --check; Check-Exit 'Publication audit'
gh auth status
if ($LASTEXITCODE -ne 0) { gh auth login --hostname github.com --web; Check-Exit 'Secure GitHub login' }
$login=gh api user --jq .login; Check-Exit 'GitHub identity'
if ($login -ne 'ssilva9912') { throw 'Authenticated GitHub account does not match ssilva9912.' }
if (-not (Test-Path -LiteralPath '.git')) { git init -b main; Check-Exit 'Git initialization' }
$remotes=@(git remote); Check-Exit 'Inspect remotes'
if ($remotes.Count -gt 0) {
  $url=git remote get-url origin; Check-Exit 'Inspect origin'
  if ($url -notmatch '^https://github\.com/ssilva9912/bls-labor-market-rag(?:\.git)?$|^git@github\.com:ssilva9912/bls-labor-market-rag(?:\.git)?$') { throw 'Existing origin differs from the approved repository.' }
}
$repo=gh repo view ssilva9912/bls-labor-market-rag --json nameWithOwner,visibility 2>$null
if ($LASTEXITCODE -eq 0) {
  $metadata=$repo | ConvertFrom-Json
  if ($metadata.visibility -ne 'PUBLIC') { throw 'Existing repository is not PUBLIC. Inspect its content and visibility before continuing.' }
  $heads=@(git ls-remote --heads https://github.com/ssilva9912/bls-labor-market-rag.git); Check-Exit 'Inspect remote history'
  if ($heads.Count -gt 0 -and $remotes.Count -eq 0) { throw 'Destination contains history. Inspect and integrate it before publishing; no overwrite attempted.' }
} else {
  gh repo create ssilva9912/bls-labor-market-rag --public --description 'BLS Labor Market RAG: controlled local RAG evaluation on eight official BLS reports'
  Check-Exit 'Create public repository'
}
if ($remotes.Count -eq 0) { git remote add origin https://github.com/ssilva9912/bls-labor-market-rag.git; Check-Exit 'Set approved origin' }
$files=(Get-Content publication_files.json -Raw | ConvertFrom-Json).files
foreach ($file in $files) { git -c core.autocrlf=false add -- $file; Check-Exit "Stage $file" }
$moved=@('score_final.py','report.py','verify_submission.py','verify_references.py','verify_ollama.py','publication_audit.py','package_submission.py','finish_publish.ps1')
$removed=@(git diff --name-only --diff-filter=D); Check-Exit 'Inspect removed paths'
foreach ($file in $removed) {
  if ($file -notin $moved) { throw "Unexpected removal: $file" }
  $group=if ($file -in @('score_final.py','report.py')) { 'evaluation' } else { 'scripts' }
  if (-not (Test-Path -LiteralPath "$group/$file")) { throw "Missing move destination: $file" }
  git add -u -- $file; Check-Exit "Stage move removal $file"
}
& $python -m scripts.publication_audit --check; Check-Exit 'Audit staged/tracked files'
git diff --cached --stat; Check-Exit 'Review staged summary'
$staged=@(git diff --cached --name-only); Check-Exit 'Inspect staged names'
foreach ($file in $staged) { if ($file -notin $files -and $file -notin $moved) { throw "Unexpected staged file: $file" } }
if ($staged.Count -gt 0) { git commit -m 'Publish BLS Labor Market RAG evaluation and offline CI'; Check-Exit 'Commit' }
git push --set-upstream origin main; Check-Exit 'Push main without force'
$commit=git rev-parse HEAD; Check-Exit 'Final commit'
Write-Host "Published https://github.com/ssilva9912/bls-labor-market-rag at $commit"
# Allow GitHub to register the push event, then inspect the actual matching run.
$run=$null
for ($attempt=0;$attempt -lt 12;$attempt++) {
  $runs=gh run list --repo ssilva9912/bls-labor-market-rag --commit $commit --json databaseId,url --limit 1 | ConvertFrom-Json
  Check-Exit 'Find Actions run'
  if ($runs.Count -gt 0) { $run=$runs[0]; break }
  Start-Sleep -Seconds 5
}
if ($null -eq $run) { throw 'Push succeeded, but no Actions run was found. Inspect the Actions tab.' }
gh run watch $run.databaseId --repo ssilva9912/bls-labor-market-rag --exit-status; Check-Exit 'GitHub Actions'
Write-Host "Passing Actions: $($run.url)"
