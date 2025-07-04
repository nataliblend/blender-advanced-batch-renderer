# Blender Add-on: Advanced Batch Renderer
#
# Version: 2.0
# Description: An advanced batch rendering tool that provides a render queue,
#              selective rendering of scenes/cameras, image vs. sequence support,
#              and real-time progress feedback.

bl_info = {
    "name": "Advanced Batch Renderer",
    "author": "Natali Vitoria (with guidance from a Mentor)",
    "version": (2, 0),
    "blender": (2, 83, 0),
    "location": "Properties > Render Properties > Batch Rendering",
    "description": "Adds a render queue for batch rendering scenes and cameras.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy
import os

# --- Global state tracking for the modal operator ---
render_state = {
    "is_rendering": False,
    "current_item_index": -1,
    "original_scene": None,
    "original_path": None,
    "timer": None
}

# -------------------------------------------------------------------
# 1. DATA STRUCTURES (Property Groups)
# -------------------------------------------------------------------

class RenderQueueItem(bpy.types.PropertyGroup):
    """An item in the render queue, representing a single camera."""
    scene_name = bpy.props.StringProperty(name="Scene")
    camera_name = bpy.props.StringProperty(name="Camera")
    
    enabled = bpy.props.BoolProperty(
        name="Enabled",
        description="Include this camera in the batch render",
        default=True
    )
    
    render_type = bpy.props.EnumProperty(
        name="Type",
        description="Choose to render a single image or an animation sequence",
        items=[('IMAGE', "Image", "Render a single frame"),
               ('ANIMATION', "Animation", "Render the scene's frame range")],
        default='IMAGE'
    )
    
    progress = bpy.props.IntProperty(
        name="Progress",
        default=0,
        min=0,
        max=100,
        subtype='PERCENTAGE'
    )
    
    status = bpy.props.StringProperty(name="Status", default="Pending")

class RenderQueuePropertyGroup(bpy.types.PropertyGroup):
    """Stores the entire list of render queue items."""
    items = bpy.props.CollectionProperty(type=RenderQueueItem)
    active_index = bpy.props.IntProperty(name="Active Index", default=0)

# -------------------------------------------------------------------
# 2. UI LIST
# -------------------------------------------------------------------

class RENDER_UL_render_queue(bpy.types.UIList):
    """Draws the render queue list."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text=f"{item.scene_name} | {item.camera_name}")
            row.separator(factor=2.0)

            if render_state["is_rendering"] and render_state["current_item_index"] == index:
                 row.prop(item, "progress", text=item.status, slider=True)
            else:
                 row.label(text=item.status)

            row.prop(item, "render_type", text="")

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)

# -------------------------------------------------------------------
# 3. OPERATORS
# -------------------------------------------------------------------

class RENDER_OT_refresh_queue(bpy.types.Operator):
    """Clears and re-populates the render queue from all scenes."""
    bl_idname = "render.refresh_queue"
    bl_label = "Refresh Render List"
    bl_description = "Scan all scenes and cameras to build the render queue"

    def execute(self, context):
        queue = context.scene.render_queue.items
        queue.clear()

        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    item = queue.add()
                    item.scene_name = scene.name
                    item.camera_name = obj.name
                    item.status = "Pending"
                    item.progress = 0
        
        self.report({'INFO'}, "Render queue refreshed.")
        return {'FINISHED'}

class RENDER_OT_move_queue_item(bpy.types.Operator):
    """Moves an item up or down in the render queue."""
    bl_idname = "render.move_queue_item"
    bl_label = "Move Queue Item"
    
    direction = bpy.props.EnumProperty(items=(('UP', 'Up', ''), ('DOWN', 'Down', '')))

    @classmethod
    def poll(cls, context):
        return context.scene.render_queue.items
    
    def execute(self, context):
        queue = context.scene.render_queue
        idx = queue.active_index
        
        if self.direction == 'UP':
            if idx > 0:
                queue.items.move(idx, idx - 1)
                queue.active_index -= 1
        elif self.direction == 'DOWN':
            if idx < len(queue.items) - 1:
                queue.items.move(idx, idx + 1)
                queue.active_index += 1
                
        return {'FINISHED'}

def get_next_render_item(context):
    """Finds the next enabled item in the queue to render."""
    queue = context.scene.render_queue.items
    start_index = render_state["current_item_index"] + 1
    
    for i in range(start_index, len(queue)):
        if queue[i].enabled:
            return i
    return -1

def render_cleanup(context):
    """Resets state and removes handlers after rendering is finished or cancelled."""
    global render_state
    
    if render_state["timer"]:
        context.window_manager.event_timer_remove(render_state["timer"])

    if render_state["original_scene"]:
        context.window.scene = render_state["original_scene"]
    if render_state["original_path"] and context.window.scene:
        context.window.scene.render.filepath = render_state["original_path"]
        
    if on_render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(on_render_pre)
    if on_render_post in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(on_render_post)
    if on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(on_render_cancel)
    
    render_state = {
        "is_rendering": False, "current_item_index": -1,
        "original_scene": None, "original_path": None, "timer": None
    }
    print("Batch Renderer: Cleanup complete.")


class RENDER_OT_render_queue(bpy.types.Operator):
    """Starts the batch rendering process using a modal operator."""
    bl_idname = "render.render_queue"
    bl_label = "Render Queue"

    @classmethod
    def poll(cls, context):
        return not render_state["is_rendering"]

    def execute(self, context):
        global render_state
        next_item_index = get_next_render_item(context)
        
        if next_item_index == -1:
            self.report({'WARNING'}, "No enabled items in the queue to render.")
            return {'CANCELLED'}

        render_state["is_rendering"] = True
        render_state["current_item_index"] = next_item_index - 1
        render_state["original_scene"] = context.window.scene
        render_state["original_path"] = context.window.scene.render.filepath
        
        bpy.app.handlers.render_pre.append(on_render_pre)
        bpy.app.handlers.render_post.append(on_render_post)
        bpy.app.handlers.render_cancel.append(on_render_cancel)

        render_state["timer"] = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        bpy.ops.render.render_queue_step('INVOKE_DEFAULT')
        
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not render_state["is_rendering"]:
            render_cleanup(context)
            self.report({'INFO'}, "Batch render finished.")
            return {'FINISHED'}

        if event.type == 'ESC':
            render_cleanup(context)
            self.report({'WARNING'}, "Batch render cancelled by user.")
            return {'CANCELLED'}
        
        if render_state["is_rendering"] and render_state["current_item_index"] != -1:
            queue = context.scene.render_queue.items
            item = queue[render_state["current_item_index"]]
            
            if item.render_type == 'ANIMATION':
                render_scene = bpy.data.scenes[item.scene_name]
                current = render_scene.frame_current
                start = render_scene.frame_start
                end = render_scene.frame_end
                total_frames = end - start + 1
                
                if total_frames > 0:
                    item.progress = int(((current - start) / total_frames) * 100)
                item.status = f"Frame {current}/{end}"

        return {'PASS_THROUGH'}


class RENDER_OT_render_queue_step(bpy.types.Operator):
    """Internal operator to process the next item in the queue."""
    bl_idname = "render.render_queue_step"
    bl_label = "Render Queue Step (Internal)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global render_state
        next_item_index = get_next_render_item(context)
        render_state["current_item_index"] = next_item_index
        
        if next_item_index == -1:
            render_state["is_rendering"] = False
            return {'FINISHED'}

        queue = context.scene.render_queue.items
        item = queue[next_item_index]
        
        render_scene = bpy.data.scenes.get(item.scene_name)
        camera = render_scene.objects.get(item.camera_name)
        
        if not render_scene or not camera:
            item.status = "Error: Scene/Cam not found"
            return self.execute(context)

        context.window.scene = render_scene
        render_scene.camera = camera
        
        if bpy.data.filepath:
            base_path = os.path.dirname(bpy.data.filepath)
        else:
            base_path = "/tmp/"
        
        filename = f"{item.scene_name}_{item.camera_name}"
        
        if item.render_type == 'IMAGE':
            render_scene.render.filepath = os.path.join(base_path, filename)
            bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
        else:
            output_dir = os.path.join(base_path, filename)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            render_scene.render.filepath = os.path.join(output_dir, '')
            bpy.ops.render.render('INVOKE_DEFAULT', animation=True)

        return {'FINISHED'}

# -------------------------------------------------------------------
# 4. APPLICATION HANDLERS
# -------------------------------------------------------------------

def on_render_pre(scene, depsgraph):
    idx = render_state["current_item_index"]
    if idx != -1:
        item = scene.render_queue.items[idx]
        item.status = "Rendering..."

def on_render_post(scene, depsgraph):
    idx = render_state["current_item_index"]
    if idx != -1:
        item = scene.render_queue.items[idx]
        
        if item.render_type == 'IMAGE':
            item.progress = 100
            item.status = "Done"
            bpy.ops.render.render_queue_step('INVOKE_DEFAULT')
        
        elif scene.frame_current == scene.frame_end:
            item.progress = 100
            item.status = "Done"
            bpy.ops.render.render_queue_step('INVOKE_DEFAULT')

def on_render_cancel(scene, depsgraph):
    print("Batch Renderer: A render job was cancelled.")
    idx = render_state["current_item_index"]
    if idx != -1:
        item = scene.render_queue.items[idx]
        item.status = "Cancelled"
        item.progress = 0
    
    global render_state
    render_state["is_rendering"] = False

# -------------------------------------------------------------------
# 5. UI PANEL
# -------------------------------------------------------------------

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
        
        row = layout.row()
        row.operator(RENDER_OT_refresh_queue.bl_idname, icon='FILE_REFRESH')
        
        render_op = row.operator(RENDER_OT_render_queue.bl_idname, icon='RENDER_ANIMATION')
        if render_state["is_rendering"]:
            render_op.enabled = False

        row = layout.row()
        row.template_list(
            "RENDER_UL_render_queue", "",
            queue, "items",
            queue, "active_index"
        )
        
        col = row.column(align=True)
        col.operator(RENDER_OT_move_queue_item.bl_idname, icon='TRIA_UP', text="").direction = 'UP'
        col.operator(RENDER_OT_move_queue_item.bl_idname, icon='TRIA_DOWN', text="").direction = 'DOWN'

# -------------------------------------------------------------------
# 6. REGISTRATION
# -------------------------------------------------------------------

classes = (
    RenderQueueItem, RenderQueuePropertyGroup, RENDER_UL_render_queue,
    RENDER_OT_refresh_queue, RENDER_OT_move_queue_item, RENDER_OT_render_queue,
    RENDER_OT_render_queue_step, RENDER_PT_batch_render_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_queue = bpy.props.PointerProperty(type=RenderQueuePropertyGroup)

def unregister():
    if render_state["is_rendering"]:
        render_cleanup(bpy.context)
        
    del bpy.types.Scene.render_queue
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
