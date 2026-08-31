from __future__ import annotations

import argparse
import hashlib
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

WIX_NS = "http://schemas.microsoft.com/wix/2006/wi"
ET.register_namespace("", WIX_NS)

UPGRADE_CODE = uuid.UUID("6fd76204-0782-5cb0-b8db-609e7c0126e1")
COMPONENT_NAMESPACE = uuid.UUID("457bb333-67aa-5e9a-8883-e60d0a1ab58c")
PRODUCT_NAMESPACE = uuid.UUID("88afef50-e2a2-5c39-b8fd-77cb79b089e6")
PACKAGE_NAMESPACE = uuid.UUID("47d4c072-e736-51f7-9b77-3d2b4d31d5c6")

PUBLISHER = "SleepMate projekt - BenWyxell - Kovács Lóránd E.V."
LEGACY_INNO_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{7E655DC3-62BC-4A9D-8EC2-B0CC579126E1}_is1"
)


def q(name: str) -> str:
    return f"{{{WIX_NS}}}{name}"


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:28]
    return f"{prefix}_{digest}"


def guid_for(kind: str, value: str) -> str:
    return "{" + str(uuid.uuid5(COMPONENT_NAMESPACE, f"{kind}:{value}")).upper() + "}"


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"MSI version must be numeric x.y.z, got {value!r}")
    major, minor, build = (int(p) for p in parts)
    if not (0 <= major <= 255 and 0 <= minor <= 255 and 0 <= build <= 65535):
        raise ValueError("MSI ProductVersion fields are outside Windows Installer limits")
    return major, minor, build


def content_hash(source_dir: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(source_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate deterministic WiX v3-compatible WXS for GNOME wixl 0.103."
    )
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()

    source_dir = Path(args.source_dir).resolve()
    output = Path(args.output).resolve()
    version = args.version.strip()
    version_tuple(version)

    if not source_dir.is_dir():
        raise SystemExit(f"Source directory does not exist: {source_dir}")
    for required in ("SleepMate.exe", "SleepMateUpdater.exe", "SleepMate.ico"):
        if not (source_dir / required).is_file():
            raise SystemExit(f"{required} missing from MSI source tree")

    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    tree_sha256 = content_hash(source_dir)
    product_code = uuid.uuid5(PRODUCT_NAMESPACE, f"SleepMate:{version}")
    package_code = uuid.uuid5(PACKAGE_NAMESPACE, f"SleepMate:{version}:{tree_sha256}")

    wix = ET.Element(q("Wix"))
    product = ET.SubElement(
        wix,
        q("Product"),
        {
            "Id": "{" + str(product_code).upper() + "}",
            "Name": "SleepMate",
            "Language": "1033",
            "Version": version,
            "Manufacturer": PUBLISHER,
            "UpgradeCode": "{" + str(UPGRADE_CODE).upper() + "}",
        },
    )
    ET.SubElement(
        product,
        q("Package"),
        {
            "Id": "{" + str(package_code).upper() + "}",
            "Description": "SleepMate PAP/CPAP therapy companion",
            "Manufacturer": PUBLISHER,
            "InstallerVersion": "500",
            "Compressed": "yes",
            "InstallScope": "perUser",
        },
    )
    ET.SubElement(
        product,
        q("MajorUpgrade"),
        {
            "AllowSameVersionUpgrades": "yes",
            "DowngradeErrorMessage": "A newer version of SleepMate is already installed.",
        },
    )
    ET.SubElement(product, q("MediaTemplate"), {"EmbedCab": "yes"})

    # Windows Installer's VersionNT/VersionNT64 values are compatibility values
    # on modern Windows and cannot reliably distinguish Windows 10/11 from older
    # NT releases. Enforce x64 here; supported Windows versions are documented
    # and the application/runtime performs the remaining compatibility checks.
    ET.SubElement(
        product,
        q("Condition"),
        {"Message": "SleepMate requires 64-bit Windows."},
    ).text = "Installed OR VersionNT64"

    legacy_prop = ET.SubElement(product, q("Property"), {"Id": "LEGACY_INNO_UNINSTALL"})
    ET.SubElement(
        legacy_prop,
        q("RegistrySearch"),
        {
            "Id": "FindLegacyInnoSleepMate",
            "Root": "HKCU",
            "Key": LEGACY_INNO_KEY,
            "Name": "UninstallString",
            "Type": "raw",
            "Win64": "no",
        },
    )
    ET.SubElement(
        product,
        q("Condition"),
        {
            "Message": (
                "A legacy SleepMate installer is still registered. "
                "Uninstall the previous SleepMate application first; "
                "your data under %LOCALAPPDATA%\\SleepMate will be preserved."
            )
        },
    ).text = "Installed OR NOT LEGACY_INNO_UNINSTALL"

    ET.SubElement(product, q("Property"), {"Id": "ARPNOREPAIR", "Value": "1"})
    ET.SubElement(
        product, q("Property"), {"Id": "ARPURLINFOABOUT", "Value": "https://mysleepmate.hu"}
    )
    ET.SubElement(
        product, q("Property"), {"Id": "ARPHELPLINK", "Value": "https://mysleepmate.hu/segitseg"}
    )
    ET.SubElement(
        product, q("Property"), {"Id": "SLEEPMATE_TREE_SHA256", "Value": tree_sha256}
    )

    ET.SubElement(
        product,
        q("Icon"),
        {
            "Id": "SleepMateIcon",
            "SourceFile": (source_dir / "SleepMate.ico").as_posix(),
        },
    )
    ET.SubElement(product, q("Property"), {"Id": "ARPPRODUCTICON", "Value": "SleepMateIcon"})

    target = ET.SubElement(product, q("Directory"), {"Id": "TARGETDIR", "Name": "SourceDir"})
    local_app = ET.SubElement(target, q("Directory"), {"Id": "LocalAppDataFolder"})
    programs = ET.SubElement(local_app, q("Directory"), {"Id": "LocalProgramsFolder", "Name": "Programs"})
    install = ET.SubElement(programs, q("Directory"), {"Id": "INSTALLFOLDER", "Name": "SleepMate"})

    program_menu = ET.SubElement(target, q("Directory"), {"Id": "ProgramMenuFolder"})
    app_menu = ET.SubElement(
        program_menu, q("Directory"), {"Id": "ApplicationProgramsFolder", "Name": "SleepMate"}
    )

    dir_elements: dict[str, ET.Element] = {"": install}

    def ensure_dir(rel_dir: Path) -> ET.Element:
        key = rel_dir.as_posix()
        if key == ".":
            key = ""
        if key in dir_elements:
            return dir_elements[key]
        parent_rel = rel_dir.parent
        parent_key = "" if parent_rel.as_posix() == "." else parent_rel.as_posix()
        parent_el = ensure_dir(Path(parent_key)) if parent_key else install
        el = ET.SubElement(
            parent_el,
            q("Directory"),
            {"Id": stable_id("Dir", key), "Name": rel_dir.name},
        )
        dir_elements[key] = el
        return el

    component_ids: list[str] = []
    for path in files:
        rel = path.relative_to(source_dir)
        rel_posix = rel.as_posix()
        parent_key = "" if rel.parent.as_posix() == "." else rel.parent.as_posix()
        directory = install if not parent_key else ensure_dir(Path(parent_key))
        component_id = stable_id("Cmp", rel_posix)
        file_id = stable_id("Fil", rel_posix)
        component = ET.SubElement(
            directory,
            q("Component"),
            {"Id": component_id, "Guid": guid_for("file", rel_posix), "Win64": "yes"},
        )
        ET.SubElement(
            component,
            q("File"),
            {
                "Id": file_id,
                "Name": path.name,
                "Source": path.as_posix(),
                "KeyPath": "yes",
            },
        )
        component_ids.append(component_id)

    registry_component = ET.SubElement(
        install,
        q("Component"),
        {"Id": "SleepMateRegistry", "Guid": guid_for("component", "registry"), "Win64": "yes"},
    )
    ET.SubElement(
        registry_component,
        q("RegistryValue"),
        {
            "Root": "HKCU",
            "Key": r"Software\SleepMate",
            "Name": "InstallPath",
            "Type": "string",
            "Value": "[INSTALLFOLDER]",
            "KeyPath": "yes",
        },
    )
    ET.SubElement(
        registry_component,
        q("RegistryValue"),
        {
            "Root": "HKCU",
            "Key": r"Software\SleepMate",
            "Name": "StatePath",
            "Type": "string",
            "Value": "[LocalAppDataFolder]SleepMate",
        },
    )
    ET.SubElement(
        registry_component,
        q("RegistryValue"),
        {
            "Root": "HKCU",
            "Key": r"Software\SleepMate",
            "Name": "Version",
            "Type": "string",
            "Value": version,
        },
    )
    component_ids.append("SleepMateRegistry")

    menu_component = ET.SubElement(
        app_menu,
        q("Component"),
        {"Id": "SleepMateStartMenu", "Guid": guid_for("component", "start-menu"), "Win64": "yes"},
    )
    ET.SubElement(
        menu_component,
        q("RegistryValue"),
        {
            "Root": "HKCU",
            "Key": r"Software\SleepMate\Installer",
            "Name": "StartMenuShortcut",
            "Type": "integer",
            "Value": "1",
            "KeyPath": "yes",
        },
    )
    ET.SubElement(
        menu_component,
        q("Shortcut"),
        {
            "Id": "SleepMateStartMenuShortcut",
            "Name": "SleepMate",
            "Description": "SleepMate PAP/CPAP therapy companion",
            "Target": "[INSTALLFOLDER]SleepMate.exe",
            "WorkingDirectory": "INSTALLFOLDER",
            "Icon": "SleepMateIcon",
            "Advertise": "no",
        },
    )
    ET.SubElement(
        menu_component,
        q("Shortcut"),
        {
            "Id": "SleepMateUninstallShortcut",
            "Name": "SleepMate eltávolítása",
            "Description": "SleepMate eltávolítása a Windows Installerrel",
            "Target": "[SystemFolder]msiexec.exe",
            "Arguments": "/x [ProductCode]",
            "Advertise": "no",
        },
    )
    ET.SubElement(
        menu_component,
        q("RemoveFolder"),
        {"Id": "RemoveSleepMateStartMenuFolder", "On": "uninstall"},
    )
    component_ids.append("SleepMateStartMenu")

    feature = ET.SubElement(
        product,
        q("Feature"),
        {
            "Id": "SleepMateFeature",
            "Title": "SleepMate",
            "Description": "SleepMate application files and Start menu integration",
            "Level": "1",
            "AllowAdvertise": "no",
            "Absent": "disallow",
        },
    )
    for component_id in component_ids:
        ET.SubElement(feature, q("ComponentRef"), {"Id": component_id})

    output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(wix)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)

    print(
        f"Generated {output} with {len(files)} payload files; "
        f"tree_sha256={tree_sha256}; product_code={product_code}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
