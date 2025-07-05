# Blender Add-on: Advanced Batch Renderer
#
# Version: 4.0.0 (MVP Test)
# Description: A simplified version to test core list population functionality.

bl_info = {
    "name": "Advanced Batch Renderer",
    "author": "Natali Vitoria (with guidance from a Mentor)",
    "version": (4, 0, 0),
    "blender": (4, 4, 0),
    "location": "Properties > Render Properties > Batch Rendering",
    "description": "Adds a render queue with pause/resume and ETA.",
    "warning": "MVP TEST VERSION",
    "doc_url": "",
    "category": "Render",
}

import bpy

# --- Simplified Global State ---
render_state = {
    "is_rendering": False
}

# -------------------------------------------------------------------
# DATA STRUCTURES & UI LIST (Unchanged)
# -------------------------------------------------------------------

class RenderQueueItem(bpy.types.PropertyGroup):
    scene_name = bpy.props.StringProperty(name="Scene")
    camera_name = bpy.props.StringProperty(name="Camera")
    enabled = bpy.props.BoolProperty(name="Enabled", default=True)
    render_type = bpy.props.EnumProperty(
        name="Type",
        items=[('IMAGE', "Image", "Image"), ('ANIMATION', "Animation", "Animation")],
        default='IMAGE'
    )
    status = bpy.props.StringProperty(name="Status", default="Pending")

class RenderQueuePropertyGroup(bpy.types.PropertyGroup):
    items = bpy.props.CollectionProperty(type=RenderQueueItem)
    active_index = bpy.props.IntProperty(name="Active Index", default=0)
    eta_display = bpy.props.StringProperty(name="ETA", default="Ready")

class RENDER_UL_render_queue(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text=f"{item.scene_name} | {item.camera_name}")
            row.separator()
            row.label(text=item.status)
            row.prop(item, "render_type", text="")

# -------------------------------------------------------------------
# OPERATORS (Simplified)
# -------------------------------------------------------------------

class RENDER_OT_refresh_queue(bpy.types.Operator):
    """(SIMPLE) Clears and re-populates the queue from the ACTIVE SCENE ONLY."""
    bl_idname = "render.refresh_queue"
    bl_label = "Refresh List (Active Scene)"

    def execute(self, context):
        print("--- Running Simple Refresh ---")
        queue = context.scene.render_queue
        
        try:
            print("Attempting to clear list...")
            queue.items.clear()
            print("List cleared successfully.")
        except Exception as e:
            print(f"ERROR while clearing list: {e}")
            self.report({'ERROR'}, f"Failed to clear list: {e}")
            return {'CANCELLED'}

        active_scene = context.scene
        print(f"Scanning active scene: '{active_scene.name}'")
        
        cameras_found = 0
        try:
            for obj in active_scene.objects:
                if obj.type == 'CAMERA':
                    item = queue.items.add()
                    item.scene_name = active_scene.name
                    item.camera_name = obj.name
                    item.status = "Pending"
                    cameras_found += 1
            
            print(f"Added {cameras_found} camera(s) to the queue.")
            queue.eta_display = f"{cameras_found} items loaded."
            self.report({'INFO'}, f"Refreshed: Found {cameras_found} cameras.")

        except Exception as e:
            print(f"ERROR while populating list: {e}")
            self.report({'ERROR'}, f"Failed to populate list: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}


class RENDER_PT_batch_render_panel(bpy.types.Panel):
    """Creates a Panel in the Render properties window"""
    bl_label = "Batch Rendering"
    bl_idname = "RENDER_PT_batch_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        queue = context.scene.render_queue
        
        row = layout.row(align=True)
        row.operator(RENDER_OT_refresh_queue.bl_idname, icon='FILE_REFRESH')
        
        layout.prop(queue, "eta_display", text="", icon='INFO')
        
        row = layout.row()
        row.template_list("RENDER_UL_render_queue", "", queue, "items", queue, "active_index")

# --- Registration ---

classes = (
    RenderQueueItem,
    RenderQueuePropertyGroup,
    RENDER_UL_render_queue,
    RENDER_OT_refresh_queue,
    RENDER_PT_batch_render_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_queue = bpy.props.PointerProperty(type=RenderQueuePropertyGroup)

def unregister():
    del bpy.types.Scene.render_queue
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
