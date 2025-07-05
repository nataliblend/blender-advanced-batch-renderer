# Blender Add-on: Advanced Batch Renderer
#
# Version: 4.0.1 (Minimal Test)
# Description: A minimal, stripped-down version to test basic registration.

bl_info = {
    "name": "Advanced Batch Renderer",
    "author": "Natali Vitoria (with guidance from a Mentor)",
    "version": (4, 0, 1),
    "blender": (4, 4, 0),
    "location": "Properties > Render Properties > Batch Rendering",
    "description": "A minimal test to ensure the add-on registers correctly.",
    "warning": "MINIMAL TEST VERSION",
    "doc_url": "",
    "category": "Render",
}

import bpy

# -------------------------------------------------------------------
# Minimal UI Panel
# -------------------------------------------------------------------

class RENDER_PT_batch_render_panel(bpy.types.Panel):
    """Creates a basic Panel in the Render properties window"""
    bl_label = "Batch Rendering"
    bl_idname = "RENDER_PT_batch_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Add-on is registered successfully!")
        layout.operator("render.refresh_queue_test")


class RENDER_OT_refresh_queue_test(bpy.types.Operator):
    """A simple test operator."""
    bl_idname = "render.refresh_queue_test"
    bl_label = "Test Refresh Button"

    def execute(self, context):
        print("Minimal test operator executed successfully.")
        self.report({'INFO'}, "Test successful!")
        return {'FINISHED'}


# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------

classes = (
    RENDER_PT_batch_render_panel,
    RENDER_OT_refresh_queue_test,
)

def register():
    print("Registering Minimal Batch Renderer...")
    for cls in classes:
        bpy.utils.register_class(cls)
    print("Registration complete.")

def unregister():
    print("Unregistering Minimal Batch Renderer...")
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("Unregistration complete.")

if __name__ == "__main__":
    register()

