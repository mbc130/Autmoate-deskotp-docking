#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import glob
import time
from pathlib import Path

def install_appimage(appimage_path):
    """
    Installs an AppImage by moving it to ~/Applications, extracting its icon,
    and creating a desktop entry.
    """
    appimage_path = Path(appimage_path).resolve()
    if not appimage_path.exists():
        print(f"Error: File not found: {appimage_path}")
        return

    # 1. Prepare Directory
    applications_dir = Path.home() / "Applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    # 2. Move/Copy AppImage
    target_path = applications_dir / appimage_path.name
    if target_path.exists():
        print(f"Warning: {target_path} already exists. Overwriting...")
    
    # Use copy instead of move if source is different filesystem or to be safe, 
    # but user asked to move/dock it so let's copy to preserve original just in case, 
    # or move if they want 'clean' desktop. The prompt says "move it to applications folder".
    # I will move it.
    try:
        shutil.move(str(appimage_path), str(target_path))
        print(f"Moved AppImage to {target_path}")
    except shutil.Error as e:
        # If it's the same file, that's fine
        if not target_path.samefile(appimage_path):
             print(f"Error moving file: {e}")
             return

    # 3. Make Executable
    target_path.chmod(target_path.stat().st_mode | 0o111)
    print("Made AppImage executable.")

    # 4. Icon Extraction
    # Create a temp dir for extraction
    temp_dir = applications_dir / ".temp_extraction"
    temp_dir.mkdir(exist_ok=True)
    
    icon_path = None
    try:
        print("Extracting AppImage icon...")
        # Run --appimage-extract inside the temp dir. 
        # AppImages usually extract to squashfs-root in the current working directory.
        subprocess.run(
            [str(target_path), "--appimage-extract"],
            cwd=str(temp_dir),
            check=True,
            stdout=subprocess.DEVNULL,  # Suppress output
            stderr=subprocess.DEVNULL
        )

        extracted_root = temp_dir / "squashfs-root"
        
        # Look for .DirIcon or typical icon locations
        candidate_icons = []
        if (extracted_root / ".DirIcon").exists():
             candidate_icons.append(extracted_root / ".DirIcon")
        
        # Also look for high-res icons in usr/share/icons
        # Often largest resolution is best.
        icon_glob = list(extracted_root.glob("usr/share/icons/hicolor/*/apps/*.png"))
        icon_glob.extend(list(extracted_root.glob("usr/share/icons/hicolor/*/apps/*.svg")))
        
        # Sort by size usually if we can, or just pick png over svg if easy, 
        # but .DirIcon is usually the "intended" icon. 
        # However, .DirIcon sometimes is a symlink to the best icon.
        
        # Let's check if we found anything
        if candidate_icons:
            # .DirIcon is often a symlink, resolving it might point to the actual file inside squashfs-root
            potential_icon = candidate_icons[0].resolve()
            if potential_icon.exists():
                icon_path = potential_icon
        elif icon_glob:
            # Pick the largest png if possible, or just the first one found
            # Heuristic: sort by path length might put larger resolution (e.g. 512x512) later or earlier?
            # 512x512 is lexically > 128x128.
            icon_glob.sort(key=lambda p: str(p)) 
            icon_path = icon_glob[-1] # Take the last one, hopefully highest res
        
        if icon_path:
            # Install Icon
            # Determine destination name
            app_name_slug = target_path.stem.lower().replace(" ", "_")
            icon_ext = icon_path.suffix
            dest_icon_name = f"{app_name_slug}_appimage_icon{icon_ext}"
            
            user_icons_dir = Path.home() / ".local/share/icons"
            user_icons_dir.mkdir(parents=True, exist_ok=True)
            
            final_icon_path = user_icons_dir / dest_icon_name
            shutil.copy(str(icon_path), str(final_icon_path))
            print(f"Icon installed to {final_icon_path}")
            icon_path_str = str(final_icon_path)
        else:
            print("Could not find icon in AppImage. Using default system icon.")
            icon_path_str = "application-x-executable"

    except Exception as e:
        print(f"Error extracting icon: {e}")
        icon_path_str = "application-x-executable"
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    # 5. Create Desktop Entry
    app_name = target_path.stem.replace("_", " ").title()
    desktop_entry_content = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec={target_path}
Icon={icon_path_str}
Categories=Utility;
Terminal=false
"""
    
    desktop_file_name = f"{target_path.stem}.desktop"
    user_applications_dir = Path.home() / ".local/share/applications"
    user_applications_dir.mkdir(parents=True, exist_ok=True)
    
    desktop_file_path = user_applications_dir / desktop_file_name
    
    with open(desktop_file_path, "w") as f:
        f.write(desktop_entry_content)
    
    # Update desktop database
    desktop_file_path.chmod(desktop_file_path.stat().st_mode | 0o111) # Make it executable just in case
    
    print(f"Desktop entry created at {desktop_file_path}")
    print("Installation Complete! You may need to log out and back in, or run 'update-desktop-database ~/.local/share/applications' if available.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 install_appimage.py <path_to_appimage>")
        sys.exit(1)
    
    install_appimage(sys.argv[1])
