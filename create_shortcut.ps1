$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("C:\Users\USER\Desktop\AI Smart Agent.lnk")
$Shortcut.TargetPath = "c:\Users\USER\.gemini\antigravity\scratch\whatsapp_server\START_GREEN_BOT.bat"
$Shortcut.IconLocation = "c:\Users\USER\.gemini\antigravity\scratch\whatsapp_server\ai_icon.ico"
$Shortcut.WorkingDirectory = "c:\Users\USER\.gemini\antigravity\scratch\whatsapp_server"
$Shortcut.Description = "Launch AI WhatsApp Bot"
$Shortcut.Save()
