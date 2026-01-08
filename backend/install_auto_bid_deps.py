#!/usr/bin/env python3
"""
Installation script for auto-bid dependencies
"""

import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    print("🚀 Installing auto-bid dependencies...")
    
    packages = [
        "selenium==4.15.2",
        "webdriver-manager==4.0.1"
    ]
    
    success_count = 0
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print(f"\n📊 Installation Summary:")
    print(f"✅ Successfully installed: {success_count}/{len(packages)} packages")
    
    if success_count == len(packages):
        print("🎉 All dependencies installed successfully!")
        print("🔧 Auto-bid functionality is now available.")
    else:
        print("⚠️ Some dependencies failed to install.")
        print("🔧 Auto-bid will use simulation mode.")
    
    print("\n📝 Note: Make sure you have Chrome browser installed for full functionality.")

if __name__ == "__main__":
    main()



