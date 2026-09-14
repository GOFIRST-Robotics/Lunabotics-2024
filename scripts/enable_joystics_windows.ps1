if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# Logitech Controller
usbipd bind --hardware-id 046d:c216
usbipd attach --wsl --hardware-id 046d:c216

# Stream Deck
usbipd bind --hardware-id 0fd9:0063
usbipd attach --wsl --hardware-id 0fd9:0063 
