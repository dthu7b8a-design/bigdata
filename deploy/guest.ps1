param([string]$Script,[string]$Output,[string]$Destination,[string]$Source,[string]$GuestDestination,[switch]$RestoreNetwork)
$ErrorActionPreference='Stop'
$vmrun=$env:VMRUN_PATH
$vmx=$env:VMX_PATH
$guestUser=$env:VM_GUEST_USER
$guestSecret=$env:VM_GUEST_PASSWORD
if(!$vmrun -or !$vmx -or !$guestUser -or !$guestSecret){
  throw 'Set VMRUN_PATH, VMX_PATH, VM_GUEST_USER and VM_GUEST_PASSWORD locally. See deploy/.env.example. No VM operation was performed.'
}
if(!(Test-Path -LiteralPath $vmrun -PathType Leaf) -or !(Test-Path -LiteralPath $vmx -PathType Leaf)){
  throw 'VMRUN_PATH and VMX_PATH must point to existing local files. No VM operation was performed.'
}
function Invoke-GuestTool([string[]]$Arguments) {
  $result=& $vmrun -gu $guestUser -gp $guestSecret @Arguments 2>&1
  if($LASTEXITCODE -ne 0){throw ('VMware guest operation failed: '+(($result -join "`n").Replace($guestSecret,'[REDACTED]')))}
}
if($Source){Invoke-GuestTool @('CopyFileFromHostToGuest',$vmx,$Source,$GuestDestination)}
if($RestoreNetwork){
  $shellQuoteEscape="'" + [char]34 + "'" + [char]34 + "'"
  $quoted="'"+$guestSecret.Replace("'",$shellQuoteEscape)+"'"
  $network="printf '%s\n' $quoted | sudo -S /bin/bash -c 'set -e; nmcli networking on; nmcli device connect ens33; nmcli -g GENERAL.CON-UUID device show ens33 | xargs -r -I{} nmcli connection modify uuid {} connection.autoconnect yes; sed -n 1,40p /var/lib/NetworkManager/NetworkManager.state; nmcli -f NAME,UUID,DEVICE,AUTOCONNECT connection show; find /etc/NetworkManager/system-connections -maxdepth 1 -type f -print' > /tmp/evcharge-stage2-network.txt 2>&1"
  Invoke-GuestTool @('runScriptInGuest',$vmx,'/bin/bash',$network)
}
if($Script){
  Invoke-GuestTool @('CopyFileFromHostToGuest',$vmx,$Script,'/tmp/evcharge-stage2-deploy.sh')
  Invoke-GuestTool @('runProgramInGuest',$vmx,'/bin/bash','/tmp/evcharge-stage2-deploy.sh')
}
if($Output){Invoke-GuestTool @('CopyFileFromGuestToHost',$vmx,$Output,$Destination)}
