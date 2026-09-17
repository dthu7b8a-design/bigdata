param([string]$Script,[string]$Output,[string]$Destination,[string]$Source,[string]$GuestDestination,[switch]$RestoreNetwork)
$ErrorActionPreference='Stop'
$vmrun='D:/workspace/02_BitDev虚拟机运行包/VMware便携运行环境/vmrun.exe'
$vmx='D:/workspace/01_用户原始资料/学生资料/01.开发环境/Ubuntu2204Bit/Ubuntu2204Bit/BitDev.vmx'
# Reuse the already authorized local connection without printing or copying its secret.
$history=Get-Content -LiteralPath 'D:/workspace/03_Codex过程资料/最终交付制作-20260907/vm.ps1' -Raw
$match=[regex]::Match($history,'-gp\s+([^\s]+)')
if(!$match.Success){throw 'Existing guest credential not found'}
$guestSecret=$match.Groups[1].Value.Trim([char]39,[char]34)
function Invoke-GuestTool([string[]]$Arguments) {
  $result=& $vmrun -gu bit -gp $guestSecret @Arguments 2>&1
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
