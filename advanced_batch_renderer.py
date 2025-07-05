# Blender Add-on: Advanced Batch Renderer
#
# Version: 3.1.17 (Stability Fix)
# Description: A production-focused batch rendering tool with a render queue,
#              pause/resume functionality, and a running ETA calculation.

bl_info = {
    "name": "Advanced Batch Renderer",
    "author": "Natali Vitoria (with guidance from a Mentor)",
    "version": (3, 1, 17),
    "blender": (4, 4, 0),
    "location": "Properties > Render Properties > Batch Rendering",
    "description": "Adds a render queue with pause/resume and ETA.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy
import os
import time
import datetime

# --- Global state tracking for the modal operator ---
render_state = {
    "is_rendering": False,
    "is_paused": False,
    "is_refreshing": False, # Flag to lock UI during refresh
    "current_item_index": -1,
    "original_scene": None,
    "original_path": None,
    "timer": None,
    "job_start_time": 0,
    "frame_times": [],
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
        name="Progress", default=0, min=0, max=100, subtype='PERCENTAGE'
    )
    
    status = bpy.props.StringProperty(name="Status", default="Pending")

class RenderQueuePropertyGroup(bpy.types.PropertyGroup):
    """Stores the entire list of render queue items and UI state."""
    items = bpy.props.CollectionProperty(type=RenderQueueItem)
    active_index = bpy.props.IntProperty(name="Active Index", default=0)
    
    eta_display = bpy.props.StringProperty(
        name="ETA Display", 
        default="Ready. Press 'Refresh' to build queue."
    )

# -------------------------------------------------------------------
# 2. UI LIST
# -------------------------------------------------------------------

class RENDER_UL_render_queue(bpy.types.UIList):
    """Draws the render queue list."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
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

# -------------------------------------------------------------------
# 3. OPERATORS
# -------------------------------------------------------------------

def populate_queue_deferred(scene_name, camera_list):
    """This function is called by a timer to populate the queue.
    It's designed to be robust and always unlock the UI."""
    global render_state
    
    scene = bpy.data.scenes.get(scene_name)
    if not scene:
        print(f"Batch Renderer Error: Could not find scene '{scene_name}' during deferred populate.")
        render_state["is_refreshing"] = False
        return

    queue = scene.render_queue
    try:
        for cam_info in camera_list:
            item = queue.items.add()
            item.scene_name = cam_info['scene']
            item.camera_name = cam_info['camera']
            item.status = "Pending"
            item.progress = 0
        
        queue.eta_display = f"{len(queue.items)} items loaded. Ready to render."
    except (AttributeError, TypeError) as e:
        error_message = f"Failed to populate queue: {e}"
        print(f"Batch Renderer Error: {error_message}")
        queue.eta_display = "Error. Please check console for details."
    finally:
        # This is critical: always unlock the UI, even if an error occurred.
        render_state["is_refreshing"] = False
    
    # Returning None ensures the timer is only run once.
    return None

class RENDER_OT_refresh_queue(bpy.types.Operator):
    """Clears and re-populates the render queue using a deferred application timer
    to avoid race conditions with Blender's UI data system."""
    bl_idname = "render.refresh_queue"
    bl_label = "Refresh Render List"
    bl_description = "Scan all scenes and cameras to build the render queue"

    @classmethod
    def poll(cls, context):
        return not render_state["is_rendering"] and not render_state["is_refreshing"]

    def execute(self, context):
        global render_state
        queue = context.scene.render_queue
        
        render_state["is_refreshing"] = True
        
        while True:
            try:
                queue.items.remove(0)
            except (IndexError, AttributeError):
                break
        
        queue.eta_display = "Loading..."
        render_state["frame_times"].clear()
        
        camera_list = []
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    camera_list.append({'scene': scene.name, 'camera': obj.name})

        # We pass the current scene name to get a valid context back in the deferred function.
        bpy.app.timers.register(lambda: populate_queue_deferred(context.scene.name, camera_list), first_interval=0.01)

        self.report({'INFO'}, "Queue refresh initiated.")
        return {'FINISHED'}


class RENDER_OT_move_queue_item(bpy.types.Operator):
    """Moves an item up or down in the render queue."""
    bl_idname = "render.move_queue_item"
    bl_label = "Move Queue Item"
    
    direction: bpy.props.EnumProperty(items=(('UP', 'Up', ''), ('DOWN', 'Down', ''))) # type: ignore
    
    @classmethod
    def poll(cls, context):
        if render_state["is_rendering"] or render_state["is_refreshing"]:
            return False
        try:
            return len(context.scene.render_queue.items) > 0
        except (AttributeError, TypeError):
            return False
    
    def execute(self, context):
        queue = context.scene.render_queue
        idx = queue.active_index
        if self.direction == 'UP' and idx > 0:
            queue.items.move(idx, idx - 1)
            queue.active_index -= 1
        elif self.direction == 'DOWN' and idx < len(queue.items) - 1:
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

def render_cleanup(context, cancelled=False):
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
    
    queue = context.scene.render_queue
    if cancelled:
        queue.eta_display = "Render cancelled."
        if 0 <= render_state["current_item_index"] < len(queue.items):
            queue.items[render_state["current_item_index"]].status = "Cancelled"
    else:
        queue.eta_display = "Render queue complete."

    render_state = {
        "is_rendering": False, "is_paused": False, "is_refreshing": False,
        "current_item_index": -1, "original_scene": None, "original_path": None,
        "timer": None, "job_start_time": 0, "frame_times": []
    }
    print("Batch Renderer: Cleanup complete.")


class RENDER_OT_render_queue_control(bpy.types.Operator):
    """Controls the main rendering process (Start/Cancel)."""
    bl_idname = "render.render_queue_control"
    bl_label = "Render Control"

    action: bpy.props.StringProperty() # type: ignore

    @classmethod
    def poll(cls, context):
        if render_state["is_refreshing"]:
            return False
        return True

    def execute(self, context):
        if self.action == 'START':
            if render_state["is_rendering"]:
                self.report({'INFO'}, "Render already in progress.")
                return {'CANCELLED'}
            return self.start_render(context)
        elif self.action == 'CANCEL':
            return self.cancel_render(context)
        return {'CANCELLED'}

    def start_render(self, context):
        global render_state
        next_item_index = get_next_render_item(context)
        if next_item_index == -1:
            self.report({'WARNING'}, "No enabled items in the queue to render.")
            return {'CANCELLED'}

        render_state.update({
            "is_rendering": True,
            "is_paused": False,
            "current_item_index": next_item_index - 1,
            "original_scene": context.window.scene,
            "original_path": context.window.scene.render.filepath,
            "frame_times": []
        })
        
        bpy.app.handlers.render_pre.append(on_render_pre)
        bpy.app.handlers.render_post.append(on_render_post)
        bpy.app.handlers.render_cancel.append(on_render_cancel)

        render_state["timer"] = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        bpy.ops.render.render_queue_step('INVOKE_DEFAULT')
        return {'RUNNING_MODAL'}

    def cancel_render(self, context):
        global render_state
        render_state["is_rendering"] = False
        bpy.ops.render.cancel()
        return {'FINISHED'}

    def modal(self, context, event):
        if not render_state["is_rendering"]:
            render_cleanup(context, cancelled=True)
            return {'FINISHED'}

        if event.type == 'ESC':
            render_cleanup(context, cancelled=True)
            self.report({'WARNING'}, "Batch render cancelled by user.")
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            self.update_eta(context)

        return {'PASS_THROUGH'}

    def update_eta(self, context):
        if not render_state["is_rendering"] or render_state["is_paused"]:
            return

        idx = render_state["current_item_index"]
        queue = context.scene.render_queue
        if not (0 <= idx < len(queue.items)):
            return

        item = queue.items[idx]
        
        if item.render_type == 'ANIMATION':
            render_scene = bpy.data.scenes[item.scene_name]
            start, end = render_scene.frame_start, render_scene.frame_end
            current = render_scene.frame_current
            
            total_frames = end - start + 1
            frames_done_in_job = current - start
            
            live_frame_time = time.time() - render_state["job_start_time"]
            
            all_times = render_state["frame_times"] + [live_frame_time]
            avg_time = sum(all_times) / len(all_times) if all_times else 0
            
            frames_remaining = total_frames - frames_done_in_job
            eta_seconds = avg_time * frames_remaining
            
            item.progress = int((frames_done_in_job / total_frames) * 100) if total_frames > 0 else 0
            item.status = f"Frame {current}/{end}"
            
            eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))
            queue.eta_display = f"Job ETA: {eta_str} | Avg: {avg_time:.2f}s/frame"

        else:
            all_times = render_state["frame_times"]
            avg_time = sum(all_times) / len(all_times) if all_times else 30
            
            remaining_jobs = 0
            for i in range(idx, len(queue.items)):
                 if queue.items[i].enabled and queue.items[i].render_type == 'IMAGE':
                     remaining_jobs += 1
            
            eta_seconds = avg_time * remaining_jobs
            eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))
            queue.eta_display = f"Queue ETA: {eta_str} | Avg: {avg_time:.2f}s/image"


class RENDER_OT_pause_resume_control(bpy.types.Operator):
    """Controls pausing and resuming the render queue."""
    bl_idname = "render.pause_resume_control"
    bl_label = "Pause/Resume Control"

    @classmethod
    def poll(cls, context):
        return render_state["is_rendering"] and not render_state["is_refreshing"]

    def execute(self, context):
        global render_state
        render_state["is_paused"] = not render_state["is_paused"]
        
        queue = context.scene.render_queue
        if render_state["is_paused"]:
            self.report({'INFO'}, "Render queue paused.")
            queue.eta_display = "PAUSED. Press Resume to continue."
            idx = render_state["current_item_index"]
            if 0 <= idx < len(queue.items):
                queue.items[idx].status = "Paused"
        else:
            self.report({'INFO'}, "Render queue resumed.")
            bpy.ops.render.render_queue_step('INVOKE_DEFAULT')
            
        return {'FINISHED'}


class RENDER_OT_render_queue_step(bpy.types.Operator):
    """Internal operator to process the next item in the queue."""
    bl_idname = "render.render_queue_step"
    bl_label = "Render Queue Step (Internal)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if render_state["is_paused"]:
            return {'CANCELLED'}
        
        next_item_index = get_next_render_item(context)
        render_state["current_item_index"] = next_item_index
        
        if next_item_index == -1:
            render_state["is_rendering"] = False
            return {'FINISHED'}

        item = context.scene.render_queue.items[next_item_index]
        render_scene = bpy.data.scenes.get(item.scene_name)
        camera = render_scene.objects.get(item.camera_name)
        
        if not render_scene or not camera:
            item.status = "Error: Not found"
            return self.execute(context)

        context.window.scene = render_scene
        render_scene.camera = camera
        
        base_path = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "/tmp/"
        filename = f"{item.scene_name}_{item.camera_name}"
        
        if item.render_type == 'IMAGE':
            render_scene.render.filepath = os.path.join(base_path, filename)
            bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
        else:
            output_dir = os.path.join(base_path, filename)
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            render_scene.render.filepath = os.path.join(output_dir, '')
            bpy.ops.render.render('INVOKE_DEFAULT', animation=True)

        return {'FINISHED'}

# -------------------------------------------------------------------
# 4. APPLICATION HANDLERS
# -------------------------------------------------------------------

def on_render_pre(scene, depsgraph):
    """Before any render starts."""
    render_state["job_start_time"] = time.time()
    idx = render_state["current_item_index"]
    if idx != -1:
        item = bpy.context.scene.render_queue.items[idx]
        item.status = "Rendering..."

def on_render_post(scene, depsgraph):
    """After a render (or a single animation frame) completes."""
    frame_duration = time.time() - render_state["job_start_time"]
    render_state["frame_times"].append(frame_duration)
    
    idx = render_state["current_item_index"]
    if idx != -1:
        item = bpy.context.scene.render_queue.items[idx]
        
        is_last_frame = (item.render_type == 'ANIMATION' and scene.frame_current == scene.frame_end)
        is_still_image = (item.render_type == 'IMAGE')

        if is_still_image or is_last_frame:
            item.progress = 100
            item.status = "Done"
            if not render_state["is_paused"]:
                bpy.ops.render.render_queue_step('INVOKE_DEFAULT')
        elif render_state["is_paused"]:
             item.status = "Paused"


def on_render_cancel(scene, depsgraph):
    """If the user cancels a render (e.g., by pressing Esc)."""
    print("Batch Renderer: A render job was cancelled.")
    idx = render_state["current_item_index"]
    if idx != -1:
        bpy.context.scene.render_queue.items[idx].status = "Cancelled"
    
    if not render_state["is_paused"]:
        bpy.ops.render.render_queue_step('INVOKE_DEFAULT')

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
        
        row = layout.row(align=True)
        
        # Draw operators and manage their enabled state
        row.operator(RENDER_OT_refresh_queue.bl_idname, icon='FILE_REFRESH')
        
        if not render_state["is_rendering"]:
            render_op = row.operator(RENDER_OT_render_queue_control.bl_idname, text="Render Queue", icon='RENDER_ANIMATION')
            render_op.action = 'START'
        else:
            cancel_op = row.operator(RENDER_OT_render_queue_control.bl_idname, text="Cancel All", icon='X')
            cancel_op.action = 'CANCEL'
            
            pause_op = row.operator(RENDER_OT_pause_resume_control.bl_idname, 
                                    text="Resume" if render_state["is_paused"] else "Pause", 
                                    icon='PLAY' if render_state["is_paused"] else 'PAUSE')

        layout.prop(queue, "eta_display", text="", icon='INFO')

        # Create a container for the list and its controls
        list_container = layout.column()
        
        # Disable the entire container when a render or refresh is active
        list_container.enabled = not (render_state["is_rendering"] or render_state["is_refreshing"])
        
        row = list_container.row()
        row.template_list("RENDER_UL_render_queue", "", queue, "items", queue, "active_index")
        
        col = row.column(align=True)
        move_op_up = col.operator(RENDER_OT_move_queue_item.bl_idname, icon='TRIA_UP', text="")
        move_op_up.direction = 'UP'
        move_op_down = col.operator(RENDER_OT_move_queue_item.bl_idname, icon='TRIA_DOWN', text="")
        move_op_down.direction = 'DOWN'


# -------------------------------------------------------------------
# 6. REGISTRATION
# -------------------------------------------------------------------

classes = (
    RenderQueueItem, RenderQueuePropertyGroup, RENDER_UL_render_queue,
    RENDER_OT_refresh_queue, RENDER_OT_move_queue_item, RENDER_OT_render_queue_control,
    RENDER_OT_pause_resume_control, RENDER_OT_render_queue_step, RENDER_PT_batch_render_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_queue = bpy.props.PointerProperty(type=RenderQueuePropertyGroup)

def unregister():
    # Ensure timers are cleaned up if the addon is disabled
    if 'populate_queue_deferred' in locals() and bpy.app.timers.is_registered(populate_queue_deferred):
        bpy.app.timers.unregister(populate_queue_deferred)
    if render_state["is_rendering"]:
        render_cleanup(bpy.context, cancelled=True)
    
    del bpy.types.Scene.render_queue
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
