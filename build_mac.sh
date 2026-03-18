#!/bin/bash
echo "========================================="
echo "UniPrint Mac App Builder"
echo "========================================="
echo ""
echo "Installing requirements..."
python3 -m pip install pyinstaller uvicorn fastapi jinja2 python-multipart "qrcode[pil]" pillow websockets watchfiles colorama
echo ""
echo "Building UniPrint.app..."
python3 -m PyInstaller --name "UniPrint" --noconfirm --onedir --windowed --add-data "templates:templates" --add-data "static:static" --hidden-import "uvicorn.logging" --hidden-import "uvicorn.loops" --hidden-import "uvicorn.loops.auto" --hidden-import "uvicorn.protocols" --hidden-import "uvicorn.protocols.http" --hidden-import "uvicorn.protocols.http.auto" --hidden-import "uvicorn.protocols.websockets" --hidden-import "uvicorn.protocols.websockets.auto" --hidden-import "uvicorn.lifespan" --hidden-import "uvicorn.lifespan.on" --hidden-import "uvicorn.lifespan.off" main.py
echo ""
echo "========================================="
echo "Build Complete!"
echo "Check the 'dist' folder for UniPrint.app"
echo "========================================="
