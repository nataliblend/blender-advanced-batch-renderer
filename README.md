# Advanced Batch Renderer for Blender

A production-focused batch rendering add-on for Blender that provides a render queue, pause/resume functionality, and a running ETA calculation. This tool was developed as a portfolio project to demonstrate Python scripting, UI/UX design, and pipeline development skills for a Technical Artist role.

---

## Features

* **Render Queue:** Automatically populates a list of all cameras from all scenes in the `.blend` file.
* **Selective Rendering:** Enable or disable individual cameras or entire scenes from the render queue.
* **Flexible Output:** Choose between rendering a single image or an animation sequence for each item in the queue.
* **Interactive Controls:**
    * **Pause/Resume:** Pause the render queue between jobs or frames and resume when ready.
    * **Cancel:** Safely stop the entire batch render at any time.
* **Time Estimation (ETA):** Provides a running estimate of the time remaining for the current job and the entire queue, which becomes more accurate as the render progresses.
* **Organize Your Workflow:** Easily reorder items in the queue to prioritize your renders.

---

## Installation

1.  Go to the **[Releases Page](https://github.com/nataliblend/blender-advanced-batch-renderer/releases)**.
2.  Download the `advanced_batch_renderer.py` file from the latest release.
3.  In Blender, go to `Edit > Preferences > Add-ons`.
4.  Click `Install...` and select the `.py` file you just downloaded.
5.  Enable the add-on by checking the box next to "Render: Advanced Batch Renderer".
6.  The panel will appear in the `Properties > Render Properties` tab.

---

## How to Use

1.  Open your Blender project.
2.  Go to the **Render Properties** tab to find the **Batch Rendering** panel.
3.  Click **Refresh Render List** to populate the queue with all your scene cameras.
4.  Enable/disable, reorder, and set the render type (Image/Animation) for each item as needed.
5.  Click **Render Queue** to begin. The UI will update with progress and ETA.

---

## For Recruiters & Developers

This project demonstrates proficiency in:

* **Blender Python API (`bpy`):** Deep knowledge of Blender's data structures (`bpy.data.scenes`, `objects`), operators, and application handlers.
* **UI/UX Development:** Creation of a user-friendly interface using `PropertyGroup`, `UIList`, and custom Panels for a seamless user experience.
* **State Management:** Implementation of a robust state machine within a `modal operator` to handle complex, long-running tasks like rendering, pausing, and resuming without freezing the UI.
* **Application Handlers:** Use of `render_pre`, `render_post`, and `render_cancel` handlers to reliably interact with Blender's core render process.
* **Software Architecture:** Designing a tool with a clean separation of data, UI, and logic for maintainability and scalability.
* **Version Control (Git):** A clear, well-documented commit history showing the iterative development of the tool from a simple script to a final product.
