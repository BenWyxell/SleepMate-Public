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


def add_button(dialog, ident, x, y, width, text, *, default=False, cancel=False):
    attrs = {
        "Id": ident,
        "Type": "PushButton",
        "X": str(x),
        "Y": str(y),
        "Width": str(width),
        "Height": "17",
        "Text": text,
    }
    if default:
        attrs["Default"] = "yes"
    if cancel:
        attrs["Cancel"] = "yes"
    return ET.SubElement(dialog, q("Control"), attrs)


def publish(control, event, value, condition="1", order=None):
    attrs = {"Event": event, "Value": value}
    if order is not None:
        attrs["Order"] = str(order)
    ET.SubElement(control, q("Publish"), attrs).text = condition


def publish_property(control, prop, value, condition="1", order=None):
    attrs = {"Property": prop, "Value": value}
    if order is not None:
        attrs["Order"] = str(order)
    ET.SubElement(control, q("Publish"), attrs).text = condition


def text_control(dialog, ident, x, y, width, height, text, *, bold=False):
    return ET.SubElement(
        dialog,
        q("Control"),
        {
            "Id": ident,
            "Type": "Text",
            "X": str(x),
            "Y": str(y),
            "Width": str(width),
            "Height": str(height),
            "Transparent": "yes",
            "NoPrefix": "yes",
            "Text": ("{\\WixUI_Font_Title}" + text) if bold else text,
        },
    )


def add_dialogs(product, sleepmate_file_id: str):
    """Create one MSI with HU/EN interactive UI and silent-install compatibility."""
    # Canonical install properties. These also remain usable from silent msiexec.
    ET.SubElement(product, q("Property"), {"Id": "SETUPLANG", "Value": "hu"})
    ET.SubElement(product, q("Property"), {"Id": "DESKTOP_SHORTCUT", "Value": "1"})
    ET.SubElement(product, q("Property"), {"Id": "START_WITH_WINDOWS", "Value": "1"})

    # Windows Installer's CheckBox table keys the checkbox by property, so HU and
    # EN dialogs cannot bind two controls to the same property. Keep language-
    # specific UI properties and copy them into the canonical properties on Next.
    for prop in (
        "DESKTOP_SHORTCUT_HU",
        "DESKTOP_SHORTCUT_EN",
        "START_WITH_WINDOWS_HU",
        "START_WITH_WINDOWS_EN",
    ):
        ET.SubElement(product, q("Property"), {"Id": prop, "Value": "1"})

    ET.SubElement(product, q("Property"), {"Id": "DefaultUIFont", "Value": "WixUI_Font_Normal"})
    ui = ET.SubElement(product, q("UI"))
    ET.SubElement(ui, q("TextStyle"), {"Id": "WixUI_Font_Normal", "FaceName": "Segoe UI", "Size": "9"})
    ET.SubElement(ui, q("TextStyle"), {"Id": "WixUI_Font_Bigger", "FaceName": "Segoe UI", "Size": "12"})
    ET.SubElement(ui, q("TextStyle"), {"Id": "WixUI_Font_Title", "FaceName": "Segoe UI", "Size": "14", "Bold": "yes"})

    cancel = ET.SubElement(ui, q("Dialog"), {"Id": "CancelDlg", "Width": "260", "Height": "85", "Title": "SleepMate Setup"})
    text_control(cancel, "CancelText", 15, 15, 230, 30, "Cancel SleepMate setup? / Megszakítod a SleepMate telepítését?")
    yes = add_button(cancel, "Yes", 85, 55, 70, "Yes / Igen", default=True)
    publish(yes, "EndDialog", "Exit")
    no = add_button(cancel, "No", 160, 55, 70, "No / Nem", cancel=True)
    publish(no, "EndDialog", "Return")

    lang = ET.SubElement(ui, q("Dialog"), {"Id": "LanguageDlg", "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
    text_control(lang, "Title", 20, 18, 330, 28, "Telepítési nyelv / Setup language", bold=True)
    text_control(lang, "Hint", 20, 55, 330, 30, "Válaszd ki a telepítő és az első beállítás nyelvét. / Choose the installer and first-run setup language.")
    group_control = ET.SubElement(lang, q("Control"), {"Id": "LanguageGroup", "Type": "RadioButtonGroup", "X": "28", "Y": "100", "Width": "260", "Height": "70", "Property": "SETUPLANG"})
    group = ET.SubElement(group_control, q("RadioButtonGroup"), {"Property": "SETUPLANG"})
    ET.SubElement(group, q("RadioButton"), {"Value": "hu", "X": "0", "Y": "0", "Width": "220", "Height": "18", "Text": "Magyar"})
    ET.SubElement(group, q("RadioButton"), {"Value": "en", "X": "0", "Y": "28", "Width": "220", "Height": "18", "Text": "English"})
    nxt = add_button(lang, "Next", 236, 243, 56, "Tovább / Next", default=True)
    publish(nxt, "NewDialog", "WelcomeHuDlg", 'SETUPLANG = "hu"', 1)
    publish(nxt, "NewDialog", "WelcomeEnDlg", 'SETUPLANG = "en"', 2)
    c = add_button(lang, "Cancel", 304, 243, 56, "Mégse", cancel=True)
    publish(c, "SpawnDialog", "CancelDlg")

    def welcome(ident: str, hu: bool):
        d = ET.SubElement(ui, q("Dialog"), {"Id": ident, "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
        text_control(d, "Title", 20, 18, 330, 28, "Üdvözöl a SleepMate" if hu else "Welcome to SleepMate", bold=True)
        text_control(
            d,
            "Body",
            20,
            58,
            330,
            80,
            "A varázsló telepíti a SleepMate alkalmazást. Az első indítás ezután végigvezet a legfontosabb beállításokon."
            if hu
            else "This wizard installs SleepMate. First run then guides you through the important initial settings.",
        )
        text_control(
            d,
            "Privacy",
            20,
            150,
            330,
            48,
            "Helyi működés az alapértelmezés. Adatvédelem: mysleepmate.hu/policy"
            if hu
            else "Local-first by default. Privacy: mysleepmate.hu/policy",
        )
        back = add_button(d, "Back", 180, 243, 56, "Vissza" if hu else "Back")
        publish(back, "NewDialog", "LanguageDlg")
        n = add_button(d, "Next", 236, 243, 56, "Tovább" if hu else "Next", default=True)
        publish(n, "NewDialog", "InstallDirHuDlg" if hu else "InstallDirEnDlg")
        c = add_button(d, "Cancel", 304, 243, 56, "Mégse" if hu else "Cancel", cancel=True)
        publish(c, "SpawnDialog", "CancelDlg")

    def install_dir(ident: str, hu: bool):
        d = ET.SubElement(ui, q("Dialog"), {"Id": ident, "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
        text_control(d, "Title", 20, 18, 330, 28, "Telepítési hely" if hu else "Install location", bold=True)
        text_control(d, "Body", 20, 58, 330, 30, "Add meg, hova kerüljön a SleepMate." if hu else "Choose where SleepMate will be installed.")
        ET.SubElement(d, q("Control"), {"Id": "Path", "Type": "PathEdit", "X": "20", "Y": "100", "Width": "330", "Height": "18", "Property": "INSTALLFOLDER"})
        text_control(d, "Default", 20, 130, 330, 45, "Alapértelmezés: LocalAppData\\Programs\\SleepMate." if hu else "Default: LocalAppData\\Programs\\SleepMate.")
        back = add_button(d, "Back", 180, 243, 56, "Vissza" if hu else "Back")
        publish(back, "NewDialog", "WelcomeHuDlg" if hu else "WelcomeEnDlg")
        n = add_button(d, "Next", 236, 243, 56, "Tovább" if hu else "Next", default=True)
        publish(n, "SetTargetPath", "INSTALLFOLDER", "1", 1)
        publish(n, "NewDialog", "OptionsHuDlg" if hu else "OptionsEnDlg", "1", 2)
        c = add_button(d, "Cancel", 304, 243, 56, "Mégse" if hu else "Cancel", cancel=True)
        publish(c, "SpawnDialog", "CancelDlg")

    def options(ident: str, hu: bool):
        desktop_prop = "DESKTOP_SHORTCUT_HU" if hu else "DESKTOP_SHORTCUT_EN"
        startup_prop = "START_WITH_WINDOWS_HU" if hu else "START_WITH_WINDOWS_EN"

        d = ET.SubElement(ui, q("Dialog"), {"Id": ident, "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
        text_control(d, "Title", 20, 18, 330, 28, "Windows beállítások" if hu else "Windows options", bold=True)
        ET.SubElement(d, q("Control"), {"Id": "Desktop", "Type": "CheckBox", "X": "25", "Y": "75", "Width": "315", "Height": "20", "Property": desktop_prop, "CheckBoxValue": "1", "Text": "Asztali SleepMate parancsikon" if hu else "Create SleepMate desktop shortcut"})
        ET.SubElement(d, q("Control"), {"Id": "Startup", "Type": "CheckBox", "X": "25", "Y": "110", "Width": "315", "Height": "20", "Property": startup_prop, "CheckBoxValue": "1", "Text": "Induljon el a Windowszal" if hu else "Start SleepMate with Windows"})
        text_control(
            d,
            "Info",
            25,
            145,
            315,
            50,
            "A Tailscale és Cloudflare az első SleepMate indításkor állítható be."
            if hu
            else "Tailscale and Cloudflare can be configured on first SleepMate launch.",
        )
        back = add_button(d, "Back", 180, 243, 56, "Vissza" if hu else "Back")
        publish(back, "NewDialog", "InstallDirHuDlg" if hu else "InstallDirEnDlg")
        n = add_button(d, "Next", 236, 243, 56, "Tovább" if hu else "Next", default=True)
        publish_property(n, "DESKTOP_SHORTCUT", f"[{desktop_prop}]", "1", 1)
        publish_property(n, "START_WITH_WINDOWS", f"[{startup_prop}]", "1", 2)
        publish(n, "AddLocal", "DesktopShortcutFeature", f'{desktop_prop} = "1"', 3)
        publish(n, "Remove", "DesktopShortcutFeature", f'{desktop_prop} <> "1"', 4)
        publish(n, "SetTargetPath", "INSTALLFOLDER", "1", 5)
        publish(n, "NewDialog", "ReadyHuDlg" if hu else "ReadyEnDlg", "1", 6)
        c = add_button(d, "Cancel", 304, 243, 56, "Mégse" if hu else "Cancel", cancel=True)
        publish(c, "SpawnDialog", "CancelDlg")

    def ready(ident: str, hu: bool):
        d = ET.SubElement(ui, q("Dialog"), {"Id": ident, "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
        text_control(d, "Title", 20, 18, 330, 28, "Telepítésre kész" if hu else "Ready to install", bold=True)
        text_control(
            d,
            "Body",
            20,
            60,
            330,
            95,
            "A SleepMate telepítésre kész. A Befejezés után automatikusan elindul az első beállítási varázsló."
            if hu
            else "SleepMate is ready to install. After Finish, the first-run setup wizard starts automatically.",
        )
        back = add_button(d, "Back", 180, 243, 56, "Vissza" if hu else "Back")
        publish(back, "NewDialog", "OptionsHuDlg" if hu else "OptionsEnDlg")
        install = add_button(d, "Install", 236, 243, 56, "Telepítés" if hu else "Install", default=True)
        publish(install, "EndDialog", "Return")
        c = add_button(d, "Cancel", 304, 243, 56, "Mégse" if hu else "Cancel", cancel=True)
        publish(c, "SpawnDialog", "CancelDlg")

    def finish(ident: str, hu: bool):
        d = ET.SubElement(ui, q("Dialog"), {"Id": ident, "Width": "370", "Height": "270", "Title": "SleepMate Setup"})
        text_control(d, "Title", 20, 18, 330, 28, "A telepítés kész" if hu else "Setup complete", bold=True)
        text_control(
            d,
            "Body",
            20,
            65,
            330,
            95,
            "A SleepMate sikeresen települt. A Befejezés elindítja az alkalmazást és az első beállítást."
            if hu
            else "SleepMate installed successfully. Finish launches the application and first-run setup.",
        )
        f = add_button(d, "Finish", 285, 243, 75, "Befejezés" if hu else "Finish", default=True)
        publish(f, "DoAction", "LaunchSleepMate", "1", 1)
        publish(f, "EndDialog", "Return", "1", 2)

    welcome("WelcomeHuDlg", True)
    welcome("WelcomeEnDlg", False)
    install_dir("InstallDirHuDlg", True)
    install_dir("InstallDirEnDlg", False)
    options("OptionsHuDlg", True)
    options("OptionsEnDlg", False)
    ready("ReadyHuDlg", True)
    ready("ReadyEnDlg", False)
    finish("ExitHuDlg", True)
    finish("ExitEnDlg", False)

    ET.SubElement(
        product,
        q("CustomAction"),
        {
            "Id": "LaunchSleepMate",
            "FileKey": sleepmate_file_id,
            "ExeCommand": "",
            "Execute": "immediate",
            "Impersonate": "yes",
            "Return": "asyncNoWait",
        },
    )
    seq = ET.SubElement(product, q("InstallUISequence"))
    ET.SubElement(seq, q("Show"), {"Dialog": "LanguageDlg", "Before": "ExecuteAction"}).text = "NOT Installed"
    ET.SubElement(seq, q("Show"), {"Dialog": "ExitHuDlg", "After": "ExecuteAction"}).text = 'NOT Installed AND SETUPLANG = "hu"'
    ET.SubElement(seq, q("Show"), {"Dialog": "ExitEnDlg", "After": "ExecuteAction"}).text = 'NOT Installed AND SETUPLANG = "en"'


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic WiX v3.14.1-compatible WXS for SleepMate.")
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
    for required in (
        "SleepMate.exe",
        "SleepMateUpdater.exe",
        "SleepMate.ico",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "PRIVACY.md",
    ):
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
            "Codepage": "1250",
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
            "SummaryCodepage": "1250",
        },
    )
    ET.SubElement(product, q("MajorUpgrade"), {"AllowSameVersionUpgrades": "yes", "DowngradeErrorMessage": "A newer version of SleepMate is already installed."})
    ET.SubElement(product, q("MediaTemplate"), {"EmbedCab": "yes"})
    ET.SubElement(product, q("Condition"), {"Message": "SleepMate requires 64-bit Windows."}).text = "Installed OR VersionNT64"

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
            "Message": "A legacy SleepMate installer is still registered. Uninstall the previous SleepMate application first; your data under %LOCALAPPDATA%\\SleepMate will be preserved."
        },
    ).text = "Installed OR NOT LEGACY_INNO_UNINSTALL"

    ET.SubElement(product, q("Property"), {"Id": "ARPNOREPAIR", "Value": "1"})
    ET.SubElement(product, q("Property"), {"Id": "ARPURLINFOABOUT", "Value": "https://mysleepmate.hu"})
    ET.SubElement(product, q("Property"), {"Id": "ARPHELPLINK", "Value": "https://mysleepmate.hu/segitseg"})
    ET.SubElement(product, q("Property"), {"Id": "SLEEPMATE_TREE_SHA256", "Value": tree_sha256})
    ET.SubElement(product, q("Icon"), {"Id": "SleepMateIcon", "SourceFile": (source_dir / "SleepMate.ico").as_posix()})
    ET.SubElement(product, q("Property"), {"Id": "ARPPRODUCTICON", "Value": "SleepMateIcon"})

    target = ET.SubElement(product, q("Directory"), {"Id": "TARGETDIR", "Name": "SourceDir"})
    local_app = ET.SubElement(target, q("Directory"), {"Id": "LocalAppDataFolder"})
    programs = ET.SubElement(local_app, q("Directory"), {"Id": "LocalProgramsFolder", "Name": "Programs"})
    install = ET.SubElement(programs, q("Directory"), {"Id": "INSTALLFOLDER", "Name": "SleepMate"})
    program_menu = ET.SubElement(target, q("Directory"), {"Id": "ProgramMenuFolder"})
    app_menu = ET.SubElement(program_menu, q("Directory"), {"Id": "ApplicationProgramsFolder", "Name": "SleepMate"})
    ET.SubElement(target, q("Directory"), {"Id": "DesktopFolder"})

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
        el = ET.SubElement(parent_el, q("Directory"), {"Id": stable_id("Dir", key), "Name": rel_dir.name})
        dir_elements[key] = el
        return el

    component_ids: list[str] = []
    file_ids: dict[str, str] = {}
    for path in files:
        rel = path.relative_to(source_dir)
        rel_posix = rel.as_posix()
        parent_key = "" if rel.parent.as_posix() == "." else rel.parent.as_posix()
        directory = install if not parent_key else ensure_dir(Path(parent_key))
        component_id = stable_id("Cmp", rel_posix)
        file_id = stable_id("Fil", rel_posix)
        file_ids[rel_posix] = file_id
        component = ET.SubElement(directory, q("Component"), {"Id": component_id, "Guid": guid_for("file", rel_posix), "Win64": "yes"})
        ET.SubElement(component, q("File"), {"Id": file_id, "Name": path.name, "Source": path.as_posix(), "KeyPath": "yes"})
        component_ids.append(component_id)

    registry_component = ET.SubElement(install, q("Component"), {"Id": "SleepMateRegistry", "Guid": guid_for("component", "registry"), "Win64": "yes"})
    ET.SubElement(registry_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate", "Name": "InstallPath", "Type": "string", "Value": "[INSTALLFOLDER]", "KeyPath": "yes"})
    ET.SubElement(registry_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate", "Name": "StatePath", "Type": "string", "Value": "[LocalAppDataFolder]SleepMate"})
    ET.SubElement(registry_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate", "Name": "Version", "Type": "string", "Value": version})
    ET.SubElement(registry_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "SetupLanguage", "Type": "string", "Value": "[SETUPLANG]"})
    ET.SubElement(registry_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "StartWithWindows", "Type": "string", "Value": "[START_WITH_WINDOWS]"})
    component_ids.append("SleepMateRegistry")

    menu_component = ET.SubElement(app_menu, q("Component"), {"Id": "SleepMateStartMenu", "Guid": guid_for("component", "start-menu"), "Win64": "yes"})
    ET.SubElement(menu_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "StartMenuShortcut", "Type": "integer", "Value": "1", "KeyPath": "yes"})
    ET.SubElement(menu_component, q("Shortcut"), {"Id": "SleepMateStartMenuShortcut", "Name": "SleepMate", "Description": "SleepMate PAP/CPAP therapy companion", "Target": "[INSTALLFOLDER]SleepMate.exe", "WorkingDirectory": "INSTALLFOLDER", "Icon": "SleepMateIcon", "Advertise": "no"})
    ET.SubElement(menu_component, q("Shortcut"), {"Id": "SleepMateUninstallShortcut", "Name": "SleepMate eltávolítása", "Description": "SleepMate eltávolítása a Windows Installerrel", "Target": "[SystemFolder]msiexec.exe", "Arguments": "/x [ProductCode]", "Advertise": "no"})
    ET.SubElement(menu_component, q("RemoveFolder"), {"Id": "RemoveSleepMateStartMenuFolder", "On": "uninstall"})
    component_ids.append("SleepMateStartMenu")

    # Keep the component rooted in INSTALLFOLDER so its registry value is a real
    # KeyPath. The Shortcut itself explicitly targets the DesktopFolder. This
    # avoids ICE18 on special-folder components without creating/removing Desktop.
    desktop_component = ET.SubElement(install, q("Component"), {"Id": "SleepMateDesktopShortcut", "Guid": guid_for("component", "desktop-shortcut"), "Win64": "yes"})
    ET.SubElement(desktop_component, q("RegistryValue"), {"Root": "HKCU", "Key": r"Software\SleepMate\Installer", "Name": "DesktopShortcut", "Type": "string", "Value": "1", "KeyPath": "yes"})
    ET.SubElement(desktop_component, q("Shortcut"), {"Id": "SleepMateDesktopShortcutLink", "Directory": "DesktopFolder", "Name": "SleepMate", "Description": "SleepMate PAP/CPAP therapy companion", "Target": "[INSTALLFOLDER]SleepMate.exe", "WorkingDirectory": "INSTALLFOLDER", "Icon": "SleepMateIcon", "Advertise": "no"})

    feature = ET.SubElement(product, q("Feature"), {"Id": "SleepMateFeature", "Title": "SleepMate", "Description": "SleepMate application files and Windows integration", "Level": "1", "AllowAdvertise": "no", "Absent": "disallow"})
    for component_id in component_ids:
        ET.SubElement(feature, q("ComponentRef"), {"Id": component_id})

    desktop_feature = ET.SubElement(product, q("Feature"), {"Id": "DesktopShortcutFeature", "Title": "SleepMate desktop shortcut", "Description": "Optional SleepMate desktop shortcut", "Level": "2", "AllowAdvertise": "no"})
    ET.SubElement(desktop_feature, q("Condition"), {"Level": "1"}).text = 'DESKTOP_SHORTCUT = "1"'
    ET.SubElement(desktop_feature, q("Condition"), {"Level": "200"}).text = 'DESKTOP_SHORTCUT <> "1"'
    ET.SubElement(desktop_feature, q("ComponentRef"), {"Id": "SleepMateDesktopShortcut"})

    add_dialogs(product, file_ids["SleepMate.exe"])

    output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(wix)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)

    print(f"Generated {output} with {len(files)} payload files; tree_sha256={tree_sha256}; product_code={product_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
