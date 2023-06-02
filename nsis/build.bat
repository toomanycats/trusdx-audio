del Setup_truSDX_Driver.exe
copy ..\trusdx-txrx.py "truSDX Driver.py"
del /S /Q "truSDX Driver.dist"
del /S /Q "truSDX Driver.build"
python -m nuitka --standalone "truSDX Driver.py"
"\Program Files (x86)\NSIS\makensis.exe" trusdx.nsi
