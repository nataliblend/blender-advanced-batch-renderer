# Blender Add-on: Batch Render All Scene Cameras
#
# This script creates a simple panel in the Render Properties to batch render
# still images from every camera in every scene of the current .blend file.
#
# To Install:
# 1. Save this code as a Python file (e.g., "batch_render_addon.py").
# 2. In Blender, go to Edit > Preferences > Add-ons.
# 3. Click "Install..." and select the saved .py file.
# 4. Enable the add-on by checking the box next to "Render: Batch Renderer".
# 5. The UI panel will appear in the Render Properties tab.

bl_info = {
    "name": "Batch Renderer",
    "author": "Your Name (with guidance from a Mentor)",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "Properties > Render Properties > Batch Rendering",
    "description": "Renders a still image from every camera in every scene.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy
import os

class RENDER_OT_batch_render_all(bpy.types.Operator):
    """Renders a still from every camera in every scene"""
    bl_idname = "render.batch_render_all_scenes"
    bl_label = "Render All Scene Cameras"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # --- Store original settings to restore them later ---
        original_scene = context.window.scene
        original_output_path = original_scene.render.filepath

        # --- Get the base path for render output ---
        # This defaults to the directory where the .blend file is saved.
        # If the file is not saved, it will use the default Blender output path.
        if bpy.data.filepath:
            base_path = os.path.dirname(bpy.data.filepath)
        else:
            self.report({'WARNING'}, "Blend file is not saved. Renders will go to the default output path.")
            base_path = original_output_path if original_output_path else "/tmp/"
        
        self.report({'INFO'}, f"Render output directory: {base_path}")

        # --- Main loop to iterate through all scene