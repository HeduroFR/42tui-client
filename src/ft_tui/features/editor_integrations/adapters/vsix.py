"""Build a minimal VSIX from the packaged plain-JavaScript extension."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="js" ContentType="application/javascript"/>
  <Default Extension="md" ContentType="text/markdown"/>
  <Default Extension="txt" ContentType="text/plain"/>
</Types>
"""


def _manifest(package: dict[str, object], version: str) -> str:
    display_name = escape(str(package.get("displayName") or "42TUI Activity"))
    description = escape(str(package.get("description") or "Send local editor activity to 42TUI."))
    engine = escape(str(package.get("engines", {}).get("vscode", "^1.80.0")))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="42tui-activity" Version="{escape(version)}" Publisher="42tui"/>
    <DisplayName>{display_name}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Tags>activity,time,tracking</Tags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}"/>
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  </Assets>
</PackageManifest>
"""


def build_vsix(destination: Path, package_dir: Path, version: str, cli_path: str) -> Path:
    """Write a VSIX containing the extension and the resolved CLI path."""
    package_dir = Path(package_dir)
    package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("extension.vsixmanifest", _manifest(package, version))
        for path in sorted(package_dir.rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(package_dir).as_posix()
                archive.write(path, f"extension/{relative}")
        archive.writestr("extension/42tui-path.txt", cli_path)
    return destination
