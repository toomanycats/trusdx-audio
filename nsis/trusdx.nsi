;SetCompressor /SOLID zlib 


!define NAME "truSDX Driver"
!define REGPATH_UNINSTSUBKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}"
Name "${NAME}"
OutFile "Setup_truSDX_Driver.exe"
ShowInstDetails show
Unicode True
RequestExecutionLevel Admin ; Request admin rights on WinVista+ (when UAC is turned on)
InstallDir "$ProgramFiles\$(^Name)"
InstallDirRegKey HKLM "${REGPATH_UNINSTSUBKEY}" "UninstallString"

!include LogicLib.nsh
!include Integration.nsh
!include WinVer.nsh
!include x64.nsh


!include MUI.nsh
!include nsDialogs.nsh
!include WinCore.nsh ; MAKELONG

;Page custom nsDialogsWelcome
Page Directory
;Page InstFiles
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE English
Page custom nsDialogsWelcome
Page custom PostInstall

Uninstpage UninstConfirm
Uninstpage InstFiles

!macro EnsureAdminRights
  UserInfo::GetAccountType
  Pop $0
  ${If} $0 != "admin" ; Require admin rights on WinNT4+
    MessageBox MB_IconStop "Administrator rights required!"
    SetErrorLevel 740 ; ERROR_ELEVATION_REQUIRED
    Quit
  ${EndIf}
!macroend

Function .onInit
  SetShellVarContext All
  !insertmacro EnsureAdminRights
FunctionEnd

Function un.onInit
  SetShellVarContext All
  !insertmacro EnsureAdminRights
FunctionEnd


Section "Program files (Required)"
  SectionIn Ro

  SetOutPath $InstDir
  WriteUninstaller "$InstDir\Uninst.exe"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "DisplayName" "${NAME}"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "DisplayIcon" "$InstDir\truSDX Driver.exe,0"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "UninstallString" '"$InstDir\Uninst.exe"'
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "QuietUninstallString" '"$InstDir\Uninst.exe" /S'
  WriteRegDWORD HKLM "${REGPATH_UNINSTSUBKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${REGPATH_UNINSTSUBKEY}" "NoRepair" 1

  File "trusdx.bmp"
  File "truSDX Driver.dist\*.*"
  File "CH341SER.EXE"
  File /R "SetupVSPE_32"
  File /R "Setup_vbcable"
SectionEnd

Section "Start Menu shortcut"
  CreateShortcut /NoWorkingDir "$SMPrograms\${NAME}.lnk" "$InstDir\truSDX Driver.exe"
SectionEnd

!macro DeleteFileOrAskAbort path
  ClearErrors
  Delete "${path}"
  IfErrors 0 +3
    MessageBox MB_ABORTRETRYIGNORE|MB_ICONSTOP 'Unable to delete "${path}"!' IDRETRY -3 IDIGNORE +2
    Abort "Aborted"
!macroend

Section -Uninstall
  Delete "$InstDir\Uninst.exe"
  !insertmacro DeleteFileOrAskAbort "$InstDir\*"
  RMDir "$InstDir"
  DeleteRegKey HKLM "${REGPATH_UNINSTSUBKEY}"

  ExecWait '"sc.exe" stop EterlogicVspeService'
  ExecWait '"sc.exe" delete EterlogicVspeService'
  ExecWait '"$InstDir\SetupVSPE_32\WixInteractor.exe" on_uninstall'

  Delete "$InstDir\SetupVSPE_32\*.*"
  Delete "$InstDir\SetupVSPE_32"

  Delete "$InstDir\Setup_vbcable\*.*"
  RMDir "$InstDir\Setup_vbcable"

  ${UnpinShortcut} "$SMPrograms\${NAME}.lnk"
  Delete "$SMPrograms\${NAME}.lnk"
SectionEnd

Function PostInstall
	Delete "$InstDir\trusdx.bmp"

	ExecWait '"$InstDir\SetupVSPE_32\WixInteractor.exe" on_install'
    ExecWait '"$InstDir\SetupVSPE_32\EterlogicVspeService.exe" install "$InstDir\SetupVSPE_32\VSPEmulator.exe" "$InstDir\SetupVSPE_32\pair.vspe" "$LocalAppdata"'
    ExecWait '"sc.exe" start EterlogicVspeService'
	
    MessageBox MB_OK "Now, CH340 USB driver will be installed. Please connect (tr)usdx to USB and select INSTALL to continue."

	ExecWait '"$InstDir\CH341SER.EXE"'

    MessageBox MB_OK "Now, VAC will be installed. Please select INSTALL to continue, you may ignore the browser page."

	${If} ${RunningX64}
		ExecWait '"$InstDir\Setup_vbcable\VBCABLE_Setup_x64.exe"'
	${Else}
		ExecWait '"$InstDir\Setup_vbcable\VBCABLE_Setup.exe"'
	${EndIf}
	;Delete "$InstDir\Setup_vbcable\*.*"
	;RMDir "$InstDir\Setup_vbcable"

	${IfNot} ${AtLeastWin8}
       MessageBox MB_OK "Unfortunatly this windows version is not supported by VSPE, download and install Virtual Serial Ports Emulator 0.937.4.747 for legacy OS systems, and create a COM8 COM9 pair."
	${EndIf}

	DetailPrint "Installation Finished"
FunctionEnd

Var DIALOG
Var HEADLINE
Var TEXT
Var IMAGECTL
Var IMAGE
Var HEADLINE_FONT

Function nsDialogsWelcome
	nsDialogs::Create 1044
	Pop $DIALOG
	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS}|${SS_BITMAP} 0 0 0 109u 193u ""
	Pop $IMAGECTL

    StrCpy $0 $InstDir\trusdx.bmp
	System::Call 'user32::LoadImage(p 0, t r0, i ${IMAGE_BITMAP}, i 0, i 0, i ${LR_LOADFROMFILE})p.s'
	Pop $IMAGE
	
	SendMessage $IMAGECTL ${STM_SETIMAGE} ${IMAGE_BITMAP} $IMAGE
	CreateFont $HEADLINE_FONT "$(^Font)" "18" "700"
	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 10u -130u 20u "(tr)uSDX Audio Driver Setup"
	Pop $HEADLINE
	SendMessage $HEADLINE ${WM_SETFONT} $HEADLINE_FONT 0

	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 32u -130u -32u "The (tr)uSDX driver makes audio streaming over USB possible. Audio cables are no longer needed! A Virtual Audio and Virtual COM Driver is installed in the background to connect to your favorite digimode application. The (tr)uSDX Driver can be started from the start menu."
	Pop $TEXT
	SetCtlColors $DIALOG 0 0xffffff
	SetCtlColors $HEADLINE 0 0xffffff
	SetCtlColors $TEXT 0 0xffffff
	nsDialogs::Show
	System::Call gdi32::DeleteObject(p$IMAGE)
FunctionEnd

Section
SectionEnd
