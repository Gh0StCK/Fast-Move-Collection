bl_info = {
    "name": "Fast Move The Collection",
    "author": "Stanislav Kolesnikov",
    "version": (3, 9, 0),
    "blender": (3, 6, 1),
    "location": "View 3D > Sidebar > FastTools",
    "description": "Move collection by active object to selected collection from list",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"
}

import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty
from bpy.app.handlers import persistent

# Dictionary to store the mapping between collection names and collections
collection_map = {}

# Function to build the collection_map dictionary
def build_collection_map(collection):
    collection_map[collection.name] = collection
    for child_collection in collection.children:
        build_collection_map(child_collection)

# Function to find a collection by name
def find_collection(name):
    return collection_map.get(name)

# Function to recursively generate submenus for all child collections
def generate_child_menus(collection):
    for child_collection in collection.children:
        if child_collection.children:
            class_name = f"CHILD_MT_{generate_class_name(child_collection.name)}"
            child_menu_class = type(
                class_name,
                (MYADDON_MT_ChildMenu,),
                {
                    "bl_label": child_collection.name,
                    "bl_idname": class_name,
                    "collection_name": child_collection.name
                }
            )
            bpy.utils.register_class(child_menu_class)
            generate_child_menus(child_collection)

# Function to generate a safe class name
def generate_class_name(name):
    return "".join([c if c.isalnum() else "_" for c in name])

# Function to compare conditions and create menu items
def compareConditions(layout, obj, ccol, attr):
    if not (obj and obj.name in ccol.objects):
        if ccol.children:
            child_menu_class = getattr(bpy.types, attr)
            layout.menu(child_menu_class.bl_idname, text=ccol.name)
        else:
            op = layout.operator("object.move_to_collection_operator", text=ccol.name)
            op.collection_name = ccol.name
    return {'FINISHED'}

# Operator class to move objects to a collection
class MoveToCollectionOperator(bpy.types.Operator):
    bl_idname = "object.move_to_collection_operator"
    bl_label = "Move the Collection"
    bl_options = {'REGISTER', 'UNDO'}
    collection_name: bpy.props.StringProperty()
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Moved To")
        box = row.box()
        box.scale_x = 2
        box.scale_y = 0.5
        box.label(text=self.collection_name)
    
    def execute(self, context):
        obj = context.active_object
        collectionTarget = self.collection_name
        scene_collection = context.scene.collection
        
        col = obj.users_collection[0]  # Current collection of selected object
        
        # Errors if Object not selected or it is None
        if obj is None or not context.object.select_get():
            self.report({'ERROR'}, "No object selected!")
            return {'CANCELLED'}

        # Errors if Object in Scene Collection
        if col.name == scene_collection.name:
            self.report({'ERROR'}, "Can't move the basic scene")
            return {'CANCELLED'}
        
        # Check if Scene Collection is the parent collection for object's collection
        current_col = next((scene_collection.name for collection in scene_collection.children
                            if col.name in collection.name),
                           None)
        
        # If Scene Collection is the parent, unlink the collection
        if current_col == scene_collection.name:
            if col.name in bpy.data.collections[collectionTarget].children:
                self.report({'WARNING'}, f"Collection '{col.name}' is already in collection '{collectionTarget}'")
                return {'CANCELLED'}
            else:
                context.scene.collection.children.unlink(col)
        
        # If Scene Collection is not the parent, unlink from other collections
        elif current_col != scene_collection.name:
            current_col = next((collection for collection in bpy.data.collections
                                if col.name in collection.children),
                               None)
            if current_col.name == collectionTarget:
                self.report({'WARNING'}, f"Collection '{col.name}' is already in collection '{collectionTarget}'")
                return {'CANCELLED'}
            current_col.children.unlink(col)
        
        # Link to the target collection
        if collectionTarget == scene_collection.name:
            context.scene.collection.children.link(col)
        else:
            bpy.data.collections[collectionTarget].children.link(col)
        
        initialize()
        
        return {'FINISHED'}

# Main menu class
class MYADDON_MT_MainMenu(bpy.types.Menu):
    bl_label = "Move The Collection"
    bl_idname = "VIEW3D_MT_collection_menu"

    def invoke(self, context, event):
        initialize()

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object
        
        # Check if the active object is in a child collection of the Scene Collection
        if not (obj and any(obj.name in collection.objects for collection in scene.collection.children)):
            layout.operator("object.move_to_collection_operator", text="Scene Collection").collection_name = scene.collection.name

        for collection in scene.collection.children:
            compareConditions(layout, obj, collection, f"CHILD_MT_{generate_class_name(collection.name)}")

# Submenu class
class MYADDON_MT_ChildMenu(bpy.types.Menu):
    bl_label = "My Sub-Menu"
    bl_idname = ""
    collection_name = ""

    def invoke(self, context, event):
        initialize()
        
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        parent_collection = find_collection(self.collection_name)

        if parent_collection:
            op = layout.operator("object.move_to_collection_operator", text=parent_collection.name)
            op.collection_name = parent_collection.name

            for child_collection in parent_collection.children:
                compareConditions(layout, obj, child_collection, f"CHILD_MT_{generate_class_name(child_collection.name)}")

# Panel class to display the Move Collection button
class OnePanel(Panel):
    bl_label = "Move The Collection"
    bl_idname = "OBJECT_PT_move_collection_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastTools"
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("wm.call_menu", text="Move Collection").name = MYADDON_MT_MainMenu.bl_idname

# Handler functions
@persistent
def depsgraph_update_handler(scene):
    # Call initialize function on every depsgraph update
    initialize()

@persistent
def load_handler(dummy):
    initialize()

def initialize():
    my_scene = bpy.context.window_manager.windows[0].scene
    build_collection_map(my_scene.collection)
    generate_child_menus(my_scene.collection)

# Register and unregister functions
classes = [
    OnePanel,
    MYADDON_MT_MainMenu,
    MoveToCollectionOperator
]

def register():   
    initialize()
    for cl in classes:
        bpy.utils.register_class(cl)    
    bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)

def unregister():
    for cls in bpy.types.__dict__.values():
        if isinstance(cls, type) and issubclass(cls, MYADDON_MT_ChildMenu):
            bpy.utils.unregister_class(cls)
    for cl in reversed(classes):
        bpy.utils.unregister_class(cl)
   
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)
    bpy.app.handlers.load_post.remove(load_handler)  

if __name__ == "__main__":
    register()
