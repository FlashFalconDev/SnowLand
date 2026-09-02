$ErrorActionPreference = 'Continue'

Write-Host 'Stopping IIS / W3SVC so it no longer owns port 80...'
Stop-Service -Name W3SVC -Force
Set-Service -Name W3SVC -StartupType Manual

Write-Host 'Opening Windows Firewall for Caddy HTTPS...'
netsh advfirewall firewall delete rule name="Caddy HTTP 80" | Out-Null
netsh advfirewall firewall delete rule name="Caddy HTTPS 443" | Out-Null
netsh advfirewall firewall delete rule name="Caddy HTTP3 443 UDP" | Out-Null
netsh advfirewall firewall add rule name="Caddy HTTP 80" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Caddy HTTPS 443" dir=in action=allow protocol=TCP localport=443
netsh advfirewall firewall add rule name="Caddy HTTP3 443 UDP" dir=in action=allow protocol=UDP localport=443

Write-Host ''
Write-Host 'Done. Caddy should now be reachable on TCP 80/443 if the router forwards them to this machine.'
Write-Host 'Press Enter to close this window.'
Read-Host
