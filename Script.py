import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d

_handler = None
offscreen = None
blur_offscreen = None
blur_shader = None
blur_batch = None

SIZE = 180

FOV_SCALE = 8.0
BLUR_RADIUS = 16.0


def create_blur():

    global blur_shader
    global blur_batch

    interface = gpu.types.GPUStageInterfaceInfo("blur_interface")
    interface.smooth('VEC2', "uv")

    info = gpu.types.GPUShaderCreateInfo()

    info.sampler(0, 'FLOAT_2D', "image")

    info.push_constant('VEC2', "texelSize")
    info.push_constant('FLOAT', "blurRadius")

    info.vertex_in(0, 'VEC2', "position")
    info.vertex_out(interface)

    info.fragment_out(0, 'VEC4', "FragColor")

    info.vertex_source("""
    void main()
    {
        uv = position / 140.0;

        gl_Position = vec4(
            uv.x * 2.0 - 1.0,
            uv.y * 2.0 - 1.0,
            0.0,
            1.0
        );
    }
    """)

    info.fragment_source("""
    void main()
    {
        vec4 color = vec4(0.0);

        for (int x = -10; x < 10; x++)
        {
            for (int y = -10; y < 10; y++)
            {
                vec2 offset = vec2(
                    float(x),
                    float(y)
                );

                color += texture(
                    image,
                    uv + offset * texelSize * blurRadius / 10.0
                );
            }
        }

        FragColor = color / 400.0;
    }
    """)

    blur_shader = gpu.shader.create_from_info(info)

    vertices = (
        (0, 0),
        (SIZE, 0),
        (SIZE, SIZE),
        (0, SIZE)
    )

    blur_batch = batch_for_shader(
        blur_shader,
        'TRI_FAN',
        {
            "position": vertices
        }
    )


def draw():

    global offscreen
    global blur_offscreen

    context = bpy.context
    region = context.region

    if region is None or region.type != 'WINDOW':
        return

    width = region.width
    height = region.height

    cx = width / 2
    cy = height / 2

    x = int(cx - SIZE / 2)
    y = int(cy - SIZE / 2)

    if offscreen is None:
        offscreen = gpu.types.GPUOffScreen(
            SIZE,
            SIZE,
            format='RGBA8'
        )

    if blur_offscreen is None:
        blur_offscreen = gpu.types.GPUOffScreen(
            SIZE,
            SIZE,
            format='RGBA8'
        )

    if blur_shader is None:
        create_blur()

    space = context.space_data
    region_3d = space.region_3d

    view_matrix = region_3d.view_matrix.copy()
    projection_matrix = region_3d.window_matrix.copy()

    projection_matrix[0][0] *= FOV_SCALE
    projection_matrix[1][1] *= FOV_SCALE

    offscreen.draw_view3d(
        context.scene,
        context.view_layer,
        space,
        region,
        view_matrix,
        projection_matrix,
        do_color_management=True
    )

    blur_offscreen.bind()

    gpu.state.depth_test_set('NONE')
    gpu.state.depth_mask_set(False)
    gpu.state.blend_set('NONE')

    gpu.state.viewport_set(
        0,
        0,
        SIZE,
        SIZE
    )

    blur_shader.bind()

    blur_shader.uniform_sampler(
        "image",
        offscreen.texture_color
    )

    blur_shader.uniform_float(
        "texelSize",
        (1.0 / SIZE, 1.0 / SIZE)
    )

    blur_shader.uniform_float(
        "blurRadius",
        BLUR_RADIUS
    )

    blur_batch.draw(blur_shader)

    blur_offscreen.unbind()

    gpu.state.depth_mask_set(False)

    draw_texture_2d(
        blur_offscreen.texture_color,
        (x, y),
        SIZE,
        SIZE
    )

    gpu.state.depth_mask_set(True)


def register():

    global _handler

    if _handler is not None:
        return

    create_blur()

    _handler = bpy.types.SpaceView3D.draw_handler_add(
        draw,
        (),
        'WINDOW',
        'POST_PIXEL'
    )

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def unregister():

    global _handler
    global offscreen
    global blur_offscreen
    global blur_shader
    global blur_batch

    if _handler is not None:

        bpy.types.SpaceView3D.draw_handler_remove(
            _handler,
            'WINDOW'
        )

        _handler = None

    if offscreen is not None:
        offscreen.free()
        offscreen = None

    if blur_offscreen is not None:
        blur_offscreen.free()
        blur_offscreen = None

    blur_shader = None
    blur_batch = None

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


if __name__ == "__main__":
    register()