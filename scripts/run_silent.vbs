Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
ProjectDir = FSO.GetParentFolderName(ScriptDir)
BatPath = ProjectDir & "\run.bat"

' Run run.bat --once completely hidden (0 = hide window, False = don't wait)
WshShell.Run """" & BatPath & """ --once", 0, True
