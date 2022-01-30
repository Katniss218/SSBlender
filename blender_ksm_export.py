import bpy
import math
import mathutils
import struct
import copy

#
# PLUGIN INFO
#

bl_info = {
    "name": "SS - Mesh Exporter",
    "category": "Object",
    "blender": (2, 80, 0)
}

#
# MESH CLASS WITH OPs
#

class Face:
    def __init__(self, i1, i2, i3):
        self.v = []
        self.v.append( i1 )
        self.v.append( i2 )
        self.v.append( i3 )
        
class Mesh:
    def __init__(self, name):
        self.name = name
        
        self.vertices = [] # Vertex positions
        self.normals = [] # Vertex normals
        self.uvs = [] # Vertex UVs
        self.is_smooth = [] # true if the vertex is smoothed with neighbors.
        self.vertex_count = 0
        
        self.faces = []
        
    def getSmoothVerticesAt( self, position ): # this returns the index for the arrays.
        ret = []
        for i in range(self.vertex_count):
            if( self.is_smooth[i] == True ):
                if( abs( self.vertices[i][0] - position[0] ) < 0.00001 and abs( self.vertices[i][1] - position[1] ) < 0.00001 and abs( self.vertices[i][2] - position[2] ) < 0.00001 ):
                    ret.append( i )
        return ret
        
    def addVertex( self, position, normal, uv, is_smooth ):
        print( "pos: %s | nrm: %s | smt: %s" % (position, normal, is_smooth) )
        
        # The new vertex is not smoothed with neighbors.
        if( not is_smooth ):
            self.normals.append( normal )
            self.vertices.append( position )
            self.uvs.append( uv )
            self.is_smooth.append( False )
            self.vertex_count += 1
            return self.vertex_count
        # The new vertex is smoothed with neighbors.
        else:
            overlapping_smooth_verts = self.getSmoothVerticesAt( position )
            # If the new vertex is smooth, and there are existing smooth vertices to merge with.
            if( overlapping_smooth_verts ):
                new_normal = normal
                for i in range( len(overlapping_smooth_verts) ):
                    # Calculate the new, interpolated normal vector
                    new_normal += self.normals[overlapping_smooth_verts[i]]
                    
                # assign the new interpolated normal to each shared smooth vertex.
                new_normal.normalize()
                for i in range( len(overlapping_smooth_verts) ):
                    self.normals[overlapping_smooth_verts[i]] = new_normal
                
                # then, if they have the same uv's, you can merge the vertices.
                #if( self.uvs[overlapping_smooth_verts][0] == uv[0] and self.uvs[overlapping_smooth_verts][1] == uv[1] ):
                #    return overlapping_smooth_verts
                # If they have different uv's, you add the new vertex with it's own uv's.
                #else:
                self.normals.append( new_normal )
                self.vertices.append( position )
                self.uvs.append( uv )
                self.is_smooth.append( True )
                self.vertex_count += 1
                return self.vertex_count
            # If the new vertex is smooth, but there are no existing smooth vertices to merge with.
            else:
                self.normals.append( normal )
                self.vertices.append( position )
                self.uvs.append( uv )
                self.is_smooth.append( True )
                self.vertex_count += 1
                return self.vertex_count
            
            
                
        
        
    def addFace( self, polygon, uv_loop, vertices ):
    #, coordmatrix ):
        # if the face we are adding is not smooth.
        #if( not polygon.use_smooth ):
        #normalmatrix = coordmatrix.inverted().transposed()
        #normal = normalmatrix @ polygon.normal
        normal = copy.copy(polygon.normal)
        normal.normalize()
        #idx0 = self.addVertex( coordmatrix @ vertices[polygon.vertices[0]].co, normal, uv_loop[polygon.loop_indices[0]].uv, polygon.use_smooth )
        #idx1 = self.addVertex( coordmatrix @ vertices[polygon.vertices[1]].co, normal, uv_loop[polygon.loop_indices[1]].uv, polygon.use_smooth )
        #idx2 = self.addVertex( coordmatrix @ vertices[polygon.vertices[2]].co, normal, uv_loop[polygon.loop_indices[2]].uv, polygon.use_smooth )
        idx0 = self.addVertex( vertices[polygon.vertices[0]].co, normal, uv_loop[polygon.loop_indices[0]].uv, polygon.use_smooth )
        idx1 = self.addVertex( vertices[polygon.vertices[1]].co, normal, uv_loop[polygon.loop_indices[1]].uv, polygon.use_smooth )
        idx2 = self.addVertex( vertices[polygon.vertices[2]].co, normal, uv_loop[polygon.loop_indices[2]].uv, polygon.use_smooth )

        self.faces.append( [idx2, idx1, idx0] )
        

    def exportVertices( self, f ):
        vertex_count = len( self.vertices )

        # Vertices (pos)
        f.write( struct.pack( ">4s", b"vert" ) )
        f.write( struct.pack( ">l", vertex_count ) )

        for i in range( vertex_count ):
            f.write( struct.pack( "<fff", self.vertices[i].x, self.vertices[i].z, self.vertices[i].y ) )
            f.write( struct.pack( "<fff", self.normals[i].x, self.normals[i].z, self.normals[i].y ) )
            f.write( struct.pack( "<ff", self.uvs[i].x, self.uvs[i].y ) )
    
    def exportFaces( self, f ):
        face_count = len(self.faces)
        
        # Faces
        f.write( struct.pack( ">4s", b"face" ) )
        f.write( struct.pack( ">l", face_count ) )

        for i in range( face_count ):
            face = self.faces[i]
            f.write( struct.pack( "<lll", face[0], face[1], face[2] ) )
        
        
exportableTypes = {
    "MESH": 1
}


#
# PLUGIN EXPORT FUNC
#

def write_to_file( self, context, filepath ):
    print( "exporting .ksm file..." )
    f = open( filepath, "wb" )

    f.write( struct.pack( ">4s", b"_KSM" ) )

    obj = context.active_object
        
    if obj.type == 'MESH':
        exported_mesh = Mesh( obj.name )
        
        # Get the mesh with modifiers applied.
        mesh = obj.evaluated_get(context.evaluated_depsgraph_get()).to_mesh()
        mesh.calc_normals_split()
        
        #coordmatrix = obj.matrix_world
        uvlayer = mesh.uv_layers.active and mesh.uv_layers.active.data
                        
        for j in range(len(mesh.polygons)):
            if( len(mesh.polygons[j].vertices) != 3 ):
                self.report({'ERROR'}, "Export Failed! - The object %s has not been fully triangulated!" % obj.name)
                return {'CANCELLED'}
            else:
                exported_mesh.addFace( mesh.polygons[j], mesh.uv_layers.active.data, mesh.vertices )
                #, coordmatrix, normalmatrix )
        
        # Export the actual thing
        exported_mesh.exportVertices( f )
        exported_mesh.exportFaces( f )

    f.close()
    return {'FINISHED'}

# ExportHelper is a helper class, defines filename and invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class ExportSomeData(Operator, ExportHelper):
    """Export scene as a Katniss's Model (.ksm) file"""
    bl_idname = "export_scene.ksm"  # important since its how bpy.ops.export_scene.ksm is constructed
    bl_label = "Export Katniss's Model"

    filename_ext = ".ksm"

    def execute(self, context):
        return write_to_file(self, context, self.filepath)

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportSomeData.bl_idname, text="Katniss's Model (.ksm)")

#
# PLUGIN MAIN
#

def register():
    print( "hi" )
    bpy.utils.register_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    print( "bye" )
    bpy.utils.unregister_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)