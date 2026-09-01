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
COMPONENT_REGISTRY_KEY = r"Software\SleepMate\Installer\Components"


def q(name: str) -> str:
    return f"{{{WIX_NS}}}{name}"


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:28]
    return f"{prefix}_{digest}"


def guid_for(kind: str, value: str) -> str:
    return "{" + str(uuid.uuid5(COMPONENT_NAMESPACE, f"{kind}:{value}")).upper() + "}"


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"MSI version must be numeric x.y.z, got {value!r}")
    major, minor, build = (int(part) for part in parts)
    if not (0 <= major <= 255 and 0 <= minor <= 255 and 0 <= build <= 65535):
        raise ValueError("MSI ProductVersion fields are outside Windows Installer limits")
    return major, minor, build


def content_hash(source_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(source_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _rtf_escape(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for char in text:
        if char == "\\":
            out.append(r"\\")
        elif char == "{":
            out.append(r"\{")
        elif char == "}":
            out.append(r"\}")
        elif char == "\n":
            out.append("\\par\n")
        else:
            code = ord(char)
            if code < 128:
                out.append(char)
            elif code <= 0xFFFF:
                signed = code if code <= 32767 else code - 65536
                out.append(f"\\u{signed}?")
            else:
                value = code - 0x10000
                high = 0xD800 + (value >> 10)
                low = 0xDC00 + (value & 0x3FF)
                out.append(f"\\u{high - 65536}?\\u{low - 65536}?")
    return "".join(out)


def write_legal_rtf(output_dir: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8", errors="replace")
    privacy_text = (repo_root / "PRIVACY.md").read_text(encoding="utf-8", errors="replace")
    combined = (
        "SLEEPMATE — JOGI FELTÉTELEK ÉS ADATVÉDELEM\n\n"
        "A telepítés folytatásával az alábbi licencfeltételeket és adatvédelmi "
        "tájékoztatót együttesen fogadod el. A dokumentumok a telepített "
        "alkalmazás mellett és a projekt nyilvános GitHub-tárhelyén külön is "
        "elérhetők.\n\n"
        "============================================================\n"
        "LICENCFELTÉTELEK\n"
        "============================================================\n\n"
        + license_text
        + "\n\n============================================================\n"
        "ADATVÉDELMI TÁJÉKOZTATÓ\n"
        "============================================================\n\n"
        + privacy_text
    )
    rtf = (
        "{\\rtf1\\ansi\\ansicpg1250\\uc1\\deff0"
        "{\\fonttbl{\\f0 Segoe UI;}}\\fs18\n"
        + _rtf_escape(combined)
        + "\n}"
    )
    target = output_dir / "SleepMate-Legal.rtf"
    target.write_text(rtf, encoding="ascii")
    return target


def add_registry_keypath(component: ET.Element, component_id: str, version: str) -> None:
    """Give profile-directory components an HKCU key path as required by ICE38."""
    ET.SubElement(
        component,
        q("RegistryValue"),
        {
            "Root": "HKCU",
            "Key": COMPONENT_REGISTRY_KEY,
            "Name": component_id,
            "Type": "string",
            "Value": version,
            "KeyPath": "yes",
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate deterministic WiX v3 WXS for the SleepMate Windows installer."
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
    output.parent.mkdir(parents=True, exist_ok=True)
    legal_rtf = write_legal_rtf(output.parent)

    wix = ET.Element(q("Wix"))
    product = ET.SubElement(
        wix,
        q("Product"),
        {
            "Id": "{" + str(product_code).upper() + "}",
            "Name": "SleepMate",
            "Language": "1038",
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
            "Description": "SleepMate PAP/CPAP terápiás társalkalmazás",
            "Manufacturer": PUBLISHER,
            "InstallerVersion": "500",
            "Compressed": "yes",
            "InstallScope": "perUser",
            "SummaryCodepage": "1250",
        },
    )
    ET.SubElement(
        product,
        q("MajorUpgrade"),
        {
            "AllowSameVersionUpgrades": "yes",
            "DowngradeErrorMessage": "A SleepMate újabb verziója már telepítve van ezen a számítógépen.",
        },
    )
    ET.SubElement(product, q("MediaTemplate"), {"EmbedCab": "yes"})

    ET.SubElement(
        product,
        q("Condition"),
        {"Message": "A SleepMate 64 bites Windows rendszert igényel."},
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
                "Egy korábbi SleepMate telepítő még regisztrálva van. "
                "Előbb távolítsd el a korábbi SleepMate alkalmazást; "
                "a %LOCALAPPDATA%\\SleepMate mappában tárolt felhasználói adatok megmaradnak."
            )
        },
    ).text = "Installed OR NOT LEGACY_INNO_UNINSTALL"

    ET.SubElement(product, q("Property"), {"Id": "ARPNOREPAIR", "Value": "1"})
    ET.SubElement(product, q("Property"), {"Id": "ARPURLINFOABOUT", "Value": "https://mysleepmate.hu"})
    ET.SubElement(product, q("Property"), {"Id": "ARPHELPLINK", "Value": "https://mysleepmate.hu/segitseg"})
    ET.SubElement(product, q("Property"), {"Id": "SLEEPMATE_TREE_SHA256", "Value": tree_sha256})
    ET.SubElement(
        product,
        q("Icon"),
        {"Id": "SleepMateIcon", "SourceFile": (source_dir / "SleepMate.ico").as_posix()},
    )
    ET.SubElement(product, q("Property"), {"Id": "ARPPRODUCTICON", "Value": "SleepMateIcon"})

    target = ET.SubElement(product, q("Directory"), {"Id": "TARGETDIR", "Name": "SourceDir"})
    local_app = ET.SubElement(target, q("Directory"), {"Id": "LocalAppDataFolder"})
    local_programs = ET.SubElement(local_app, q("Directory"), {"Id": "LocalProgramsFolder", "Name": "Programs"})
    install = ET.SubElement(local_programs, q("Directory"), {"Id": "INSTALLFOLDER", "Name": "SleepMate"})

    program_menu = ET.SubElement(target, q("Directory"), {"Id": "ProgramMenuFolder"})
    app_menu = ET.SubElement(program_menu, q("Directory"), {"Id": "ApplicationProgramsFolder", "Name": "SleepMate"})
    desktop = ET.SubElement(target, q("Directory"), {"Id": "DesktopFolder"})

    directory_elements: dict[str, ET.Element] = {"": install}
    directory_ids: dict[str, str] = {"": "INSTALLFOLDER"}

    def ensure_dir(rel_dir: Path) -> ET.Element:
        key = rel_dir.as_posix()
        if key == ".":
            key = ""
        if key in directory_elements:
            return directory_elements[key]
        parent_key = "" if rel_dir.parent.as_posix() == "." else rel_dir.parent.as_posix()
        parent = ensure_dir(Path(parent_key)) if parent_key else install
        directory_id = stable_id("Dir", key)
        element = ET.SubElement(parent, q("Directory"), {"Id": directory_id, "Name": rel_dir.name})
        directory_elements[key] = element
        directory_ids[key] = directory_id
        return element

    core_component_ids: list[str] = []
    main_exe_file_id = ""

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
        # Files under LocalAppDataFolder are profile resources. ICE38 requires
        # the component key path to be an HKCU registry value, not the file.
        add_registry_keypath(component, component_id, version)
        ET.SubElement(
            component,
            q("File"),
            {"Id": file_id, "Name": path.name, "Source": path.as_posix()},
        )
        if rel_posix == "SleepMate.exe":
            main_exe_file_id = file_id
        core_component_ids.append(component_id)

    if not main_exe_file_id:
        raise SystemExit("SleepMate.exe file id was not generated")

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
        {"Root": "HKCU", "Key": r"Software\SleepMate", "Name": "StatePath", "Type": "string", "Value": "[LocalAppDataFolder]SleepMate"},
    )
    ET.SubElement(
        registry_component,
        q("RegistryValue"),
        {"Root": "HKCU", "Key": r"Software\SleepMate", "Name": "Version", "Type": "string", "Value": version},
    )
    core_component_ids.append("SleepMateRegistry")

    # ICE64 requires every authored directory below a user-profile directory to
    # appear in the RemoveFile table. RemoveFolder only deletes an empty folder,
    # so LocalProgramsFolder is safe even when other per-user applications live there.
    cleanup_component = ET.SubElement(
        install,
        q("Component"),
        {"Id": "SleepMateDirectoryCleanup", "Guid": guid_for("component", "directory-cleanup"), "Win64": "yes"},
    )
    add_registry_keypath(cleanup_component, "SleepMateDirectoryCleanup", version)
    for key, directory_id in sorted(directory_ids.items(), key=lambda item: (item[0].count("/"), item[0]), reverse=True):
        suffix = key or "install-root"
        ET.SubElement(
            cleanup_component,
            q("RemoveFolder"),
            {"Id": stable_id("RmDir", suffix), "Directory": directory_id, "On": "uninstall"},
        )
    ET.SubElement(
        cleanup_component,
        q("RemoveFolder"),
        {"Id": "RemoveLocalProgramsFolderIfEmpty", "Directory": "LocalProgramsFolder", "On": "uninstall"},
    )
    core_component_ids.append("SleepMateDirectoryCleanup")

    menu_component = ET.SubElement(
        app_menu,
        q("Component"),
        {"Id": "SleepMateStartMenu", "Guid": guid_for("component", "start-menu"), "Win64": "yes"},
    )
    ET.SubElement(
        menu_component,
        q("RegistryValue"),
        {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "StartMenuShortcut", "Type": "integer", "Value": "1", "KeyPath": "yes"},
    )
    ET.SubElement(
        menu_component,
        q("Shortcut"),
        {"Id": "SleepMateStartMenuShortcut", "Name": "SleepMate", "Description": "SleepMate PAP/CPAP terápiás társalkalmazás", "Target": "[INSTALLFOLDER]SleepMate.exe", "WorkingDirectory": "INSTALLFOLDER", "Icon": "SleepMateIcon", "Advertise": "no"},
    )
    ET.SubElement(
        menu_component,
        q("Shortcut"),
        {"Id": "SleepMateUninstallShortcut", "Name": "SleepMate eltávolítása", "Description": "SleepMate eltávolítása a Windows Installerrel", "Target": "[SystemFolder]msiexec.exe", "Arguments": "/x [ProductCode]", "Advertise": "no"},
    )
    ET.SubElement(menu_component, q("RemoveFolder"), {"Id": "RemoveSleepMateStartMenuFolder", "On": "uninstall"})

    desktop_component = ET.SubElement(
        desktop,
        q("Component"),
        {"Id": "SleepMateDesktopShortcut", "Guid": guid_for("component", "desktop-shortcut"), "Win64": "yes"},
    )
    ET.SubElement(
        desktop_component,
        q("RegistryValue"),
        {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "DesktopShortcut", "Type": "integer", "Value": "1", "KeyPath": "yes"},
    )
    ET.SubElement(
        desktop_component,
        q("Shortcut"),
        {"Id": "SleepMateDesktopShortcutLink", "Name": "SleepMate", "Description": "SleepMate PAP/CPAP terápiás társalkalmazás", "Target": "[INSTALLFOLDER]SleepMate.exe", "WorkingDirectory": "INSTALLFOLDER", "Icon": "SleepMateIcon", "Advertise": "no"},
    )

    startup_component = ET.SubElement(
        install,
        q("Component"),
        {"Id": "SleepMateStartup", "Guid": guid_for("component", "startup"), "Win64": "yes"},
    )
    ET.SubElement(
        startup_component,
        q("RegistryValue"),
        {"Root": "HKCU", "Key": r"Software\Microsoft\Windows\CurrentVersion\Run", "Name": "SleepMate", "Type": "string", "Value": '\"[INSTALLFOLDER]SleepMate.exe\"', "KeyPath": "yes"},
    )

    feature = ET.SubElement(
        product,
        q("Feature"),
        {"Id": "SleepMateFeature", "Title": "SleepMate", "Description": "A SleepMate alkalmazás és a szükséges programfájlok.", "Level": "1", "Display": "expand", "AllowAdvertise": "no", "Absent": "disallow"},
    )
    for component_id in core_component_ids:
        ET.SubElement(feature, q("ComponentRef"), {"Id": component_id})

    start_feature = ET.SubElement(feature, q("Feature"), {"Id": "StartMenuFeature", "Title": "Start menü parancsikon", "Description": "SleepMate parancsikon és eltávolítási parancs a Start menüben.", "Level": "1", "AllowAdvertise": "no"})
    ET.SubElement(start_feature, q("ComponentRef"), {"Id": "SleepMateStartMenu"})

    desktop_feature = ET.SubElement(feature, q("Feature"), {"Id": "DesktopShortcutFeature", "Title": "Asztali parancsikon", "Description": "SleepMate parancsikon létrehozása az Asztalon.", "Level": "1", "AllowAdvertise": "no"})
    ET.SubElement(desktop_feature, q("ComponentRef"), {"Id": "SleepMateDesktopShortcut"})

    startup_feature = ET.SubElement(feature, q("Feature"), {"Id": "StartupFeature", "Title": "Automatikus indítás a Windowszal", "Description": "A SleepMate automatikusan elindul a felhasználói bejelentkezés után.", "Level": "2", "AllowAdvertise": "no"})
    ET.SubElement(startup_feature, q("ComponentRef"), {"Id": "SleepMateStartup"})

    ET.SubElement(product, q("Property"), {"Id": "WIXUI_INSTALLDIR", "Value": "INSTALLFOLDER"})
    ET.SubElement(product, q("Property"), {"Id": "WIXUI_EXITDIALOGOPTIONALCHECKBOXTEXT", "Value": "SleepMate indítása"})
    ET.SubElement(product, q("Property"), {"Id": "WIXUI_EXITDIALOGOPTIONALCHECKBOX", "Value": "1"})
    ET.SubElement(product, q("WixVariable"), {"Id": "WixUILicenseRtf", "Value": legal_rtf.as_posix()})
    ET.SubElement(product, q("UIRef"), {"Id": "WixUI_FeatureTree"})
    ET.SubElement(product, q("UIRef"), {"Id": "WixUI_ErrorProgressText"})

    ET.SubElement(
        product,
        q("CustomAction"),
        {"Id": "LaunchSleepMate", "FileKey": main_exe_file_id, "ExeCommand": "", "Execute": "immediate", "Return": "asyncNoWait", "Impersonate": "yes"},
    )
    ui = ET.SubElement(product, q("UI"))
    publish = ET.SubElement(
        ui,
        q("Publish"),
        {"Dialog": "ExitDialog", "Control": "Finish", "Event": "DoAction", "Value": "LaunchSleepMate", "Order": "1"},
    )
    publish.text = "WIXUI_EXITDIALOGOPTIONALCHECKBOX = 1 AND NOT Installed"

    tree = ET.ElementTree(wix)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)

    print(
        f"Generated {output} with {len(files)} payload files; "
        f"tree_sha256={tree_sha256}; product_code={product_code}; "
        "wizard=WixUI_FeatureTree; language=hu-HU; profile-components=HKCU-keypath; cleanup=RemoveFolder"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
