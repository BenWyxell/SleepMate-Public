Option Explicit
Dim shell, fso, base, shortcut, shortcutPath, iconPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
iconPath = base & "\SleepMate.ico"
shortcutPath = base & "\SleepMate.lnk"

' Keep a SleepMate shortcut next to this script and use the bundled icon.
On Error Resume Next
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
shortcut.Arguments = Chr(34) & base & "\SleepMate.vbs" & Chr(34)
shortcut.WorkingDirectory = base
shortcut.IconLocation = iconPath & ",0"
shortcut.Description = "SleepMate"
shortcut.Save
On Error GoTo 0

shell.Run "pythonw.exe """ & base & "\sleepmate_tray.pyw""", 0, False
