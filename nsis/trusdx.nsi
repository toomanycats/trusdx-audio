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

!include nsDialogs.nsh
!include WinCore.nsh ; MAKELONG
!include MUI.nsh


;Page custom nsDialogsWelcome
Page Directory
Page InstFiles
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

  ;!tempfile APP
  ;File "/oname=$InstDir\MyApp.exe" "${APP}" ; Pretend that we have a real application to install
  ;!delfile "${APP}"
  ;File *
  File "trusdx.bmp"
  File "Setup_trusdx\*.*"
  File /R "Setup_vbcable"
  File "Setup_com0com_x64.exe"
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

  ${UnpinShortcut} "$SMPrograms\${NAME}.lnk"
  Delete "$SMPrograms\${NAME}.lnk"
SectionEnd



!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE English

!macro BeginControlsTestPage title
	nsDialogs::Create 1018
	Pop $0
	${NSD_SetText} $hWndParent "$(^Name): ${title}"
!macroend

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

	;nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 32u -130u -32u "This  installs a (tr)uSDX driver, a Virtual Audio and Serial COM Interface. It makes audio streaming possible over USB. Audio cables are no longer needed to connect the (tr)uSDX to your favorite digimode app, and you can still enjoying CAT control! 73, Guido PE1NNZ"
	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 32u -130u -32u "The (tr)uSDX driver makes audio streaming over USB possible. Audio cables are no longer needed! A Virtual Audio and Virtual COM Driver is installed in the background to connect to your favorite digimode application. The (tr)uSDX Driver can be started from the start menu."
	Pop $TEXT
	SetCtlColors $DIALOG 0 0xffffff
	SetCtlColors $HEADLINE 0 0xffffff
	SetCtlColors $TEXT 0 0xffffff
	nsDialogs::Show
	System::Call gdi32::DeleteObject(p$IMAGE)
FunctionEnd

Function PostInstall
      MessageBox MB_OK "Now, VB-Audio Cable and COM0COM will be installed. Please select INSTALL DRIVER, and CLOSE the browser and continue with the COM0COM setup."

	ExecWait '"$InstDir\Setup_vbcable\VBCABLE_Setup_x64.exe"'

	ExecWait '"$InstDir\Setup_com0com_x64.exe"'

	MessageBox MB_YESNO|MB_ICONQUESTION "Reboot the system?" IDNO +2
		Reboot
FunctionEnd
