extends SceneTree

const VignetteView = preload("res://scripts/vignette_view.gd")
const ContentLoader = preload("res://scripts/content_loader.gd")
var checks: int = 0
var failures: Array[String] = []


class InvalidVignetteLoader:
	extends ContentLoader

	func read_json(raw: Variant) -> Dictionary:
		var data := super.read_json(raw)
		if data.has("background"):
			data = data.duplicate(true)
			data.background.vignette.step = 0
		return data


func _initialize() -> void:
	call_deferred("run_tests")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func screenshot(game: Node2D, suffix: String) -> void:
	var prefix: String = game.option("screenshot-prefix")
	if not prefix.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(prefix + "-" + suffix + ".png") == OK, "Vignette screenshot saves: " + suffix)


func pixel_at(image: Image, game: Node2D, point: Vector2) -> Color:
	# ViewportTexture omits the letterbox bars: use stretch, not window final transform.
	var pixel := Vector2i(get_root().get_stretch_transform() * game.get_global_transform_with_canvas() * point)
	return image.get_pixelv(pixel)


func rendered_comparison(game: Node2D, label: String) -> void:
	game.update_hover(game.views[0].position)
	check(game.name_view.visible and game.bubbles[0].visible, label + ": foreground UI is actually visible for the depth test")
	game.vignette.visible = true
	await RenderingServer.frame_post_draw
	var enabled := get_root().get_texture().get_image()
	game.vignette.visible = false
	await RenderingServer.frame_post_draw
	var disabled := get_root().get_texture().get_image()
	game.vignette.visible = true
	check(pixel_at(enabled, game, Vector2(4, 270)).r < pixel_at(disabled, game, Vector2(4, 270)).r, label + ": actual background edge is darker")
	check(pixel_at(enabled, game, Vector2(480, 270)) == pixel_at(disabled, game, Vector2(480, 270)), label + ": center is unchanged")
	for point in [game.views[0].position, Vector2(48, 400), game.bubbles[0].position + Vector2(15, 15), game.name_view.position + Vector2(3, 3)]:
		check(game.vignette.texture.get_image().get_pixelv(Vector2i(point)).a > 0, label + ": foreground sample lies inside the mask's border")
		check(pixel_at(enabled, game, point) == pixel_at(disabled, game, point), label + ": foreground character/water/bubble/name is not dimmed")


func rendered_tests(game: Node2D, settings: Dictionary) -> void:
	if DisplayServer.get_name() == "headless":
		return
	# Save the real shared settings before using a stronger mask for depth checks.
	await screenshot(game, "enabled")
	game.vignette.visible = false
	await screenshot(game, "disabled")
	game.vignette.visible = true
	var original_texture: Texture2D = game.vignette.texture
	var strong := settings.duplicate(true)
	strong.alpha_start = 200
	strong.min_alpha = 100
	game.vignette.texture = ImageTexture.create_from_image(VignetteView.render_mask(strong, Vector2i(960, 540)))
	await rendered_comparison(game, "960x540")
	var original_size := get_root().size
	get_root().size = Vector2i(1280, 1024)
	await process_frame
	game.refresh_views()
	await rendered_comparison(game, "Letterboxed window")
	game.vignette.texture = original_texture
	await screenshot(game, "letterbox")
	get_root().size = original_size
	await process_frame
	var toggle := InputEventKey.new()
	toggle.keycode = KEY_F11
	toggle.pressed = true
	get_root().push_input(toggle)
	await process_frame
	await RenderingServer.frame_post_draw
	check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN, "F11 enters fullscreen with background mask")
	game.refresh_views()
	game.update_hover(game.views[0].position)
	await screenshot(game, "fullscreen")
	game.vignette.texture = ImageTexture.create_from_image(VignetteView.render_mask(strong, Vector2i(960, 540)))
	await rendered_comparison(game, "Fullscreen")
	game.vignette.texture = original_texture
	get_root().push_input(toggle)
	await process_frame
	await RenderingServer.frame_post_draw
	check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED, "F11 returns to windowed mode with background mask")


func run_tests() -> void:
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var loader := ContentLoader.new()
	var data := loader.load_project(root)
	check(not data.is_empty(), "Shared source room loads: " + loader.error)
	if data.is_empty():
		finish()
		return
	var settings: Dictionary = data.room.background.vignette
	check(VignetteView.validate(settings, Vector2i(960, 540)).is_empty(), "Shared room's vignette settings are valid")
	for bad in [null, [], "mask"]:
		check(not VignetteView.validate(bad, Vector2i(960, 540)).is_empty(), "Non-object vignette is rejected")
	for field in ["max_inset", "step", "border_width", "radius", "alpha_start", "alpha_divisor", "min_alpha"]:
		for bad in [null, true, "8", 1.5, NAN, INF, -1, 1001]:
			var invalid := settings.duplicate(true)
			invalid[field] = bad
			check(not VignetteView.validate(invalid, Vector2i(960, 540)).is_empty(), "Invalid numeric vignette setting is rejected: " + field + "=" + str(bad))
	for bad in [[], [0, 0], [0, 0, 256], [0, -1, 4], [false, 0, 4], [0, 0, 4.5], [0, 0, INF]]:
		var invalid := settings.duplicate(true)
		invalid.color = bad
		check(not VignetteView.validate(invalid, Vector2i(960, 540)).is_empty(), "Invalid color is rejected")
	for field in ["step", "border_width", "alpha_divisor"]:
		var invalid := settings.duplicate(true)
		invalid[field] = 0
		check(not VignetteView.validate(invalid, Vector2i(960, 540)).is_empty(), "Required-positive field rejects zero: " + field)
	var invalid_loader := InvalidVignetteLoader.new()
	check(invalid_loader.load_project(root).is_empty() and "background.vignette.step" in invalid_loader.error, "Project load rejects zero step instead of entering an invalid render loop")
	var mask := VignetteView.render_mask(settings, Vector2i(960, 540))
	check(mask.get_size() == Vector2i(960, 540), "Mask covers internal room coordinates")
	check(mask.get_pixel(480, 270).a == 0 and mask.get_pixel(0, 0).a == 0, "Center and outside rounded corners stay transparent")
	check(is_equal_approx(mask.get_pixel(4, 270).a, 13.0 / 255), "Outermost border uses alpha_start")
	check(is_equal_approx(mask.get_pixel(8, 270).a, 13.0 / 255), "Overlapping borders overwrite instead of accumulating alpha")
	check(is_equal_approx(mask.get_pixel(24, 270).a, 11.0 / 255), "Inset opacity follows integer alpha_divisor")
	check(is_equal_approx(mask.get_pixel(104, 270).a, 3.0 / 255) and mask.get_pixel(120, 270).a == 0, "max_inset is exclusive and interior remains clear")
	check(mask.get_pixel(480, 4) == mask.get_pixel(4, 270), "Vertical inset uses the source's half-height spacing")
	var symmetric := true
	for point in [Vector2i(20, 20), Vector2i(4, 270), Vector2i(52, 60), Vector2i(480, 4)]:
		symmetric = symmetric and mask.get_pixelv(point) == mask.get_pixel(959 - point.x, point.y) and mask.get_pixelv(point) == mask.get_pixel(point.x, 539 - point.y)
	check(symmetric, "Rounded mask is symmetric on both axes")
	var disabled := settings.duplicate(true)
	disabled.max_inset = 0
	check(VignetteView.validate(disabled, Vector2i(960, 540)).is_empty() and VignetteView.render_mask(disabled, Vector2i(960, 540)).is_invisible(), "Zero max_inset disables vignette")
	disabled.max_inset = settings.max_inset
	disabled.alpha_start = 0
	disabled.min_alpha = 0
	check(VignetteView.validate(disabled, Vector2i(960, 540)).is_empty() and VignetteView.render_mask(disabled, Vector2i(960, 540)).is_invisible(), "Zero alpha settings also stay completely transparent")
	var custom := {"color": [120, 30, 10], "max_inset": 12, "step": 4, "border_width": 6, "radius": 0, "alpha_start": 3, "alpha_divisor": 1, "min_alpha": 2}
	var custom_image := VignetteView.render_mask(custom, Vector2i(64, 36))
	check(custom_image.get_pixel(0, 0) == Color8(120, 30, 10, 3) and custom_image.get_pixel(8, 18) == Color8(120, 30, 10, 2), "Custom color, square corners and minimum alpha are honored")
	custom.radius = 500
	custom.border_width = 100
	check(not VignetteView.render_mask(custom, Vector2i(64, 36)).is_invisible(), "Large valid radius and border width clamp safely to small rectangles")
	var game := (load("res://main.tscn") as PackedScene).instantiate()
	get_root().add_child(game)
	game.set_process(false)
	check(game.vignette.get_index() < game.world.get_index() and game.vignette.z_index == 0, "Vignette draws before all world children, including water")
	check(not game.vignette.centered and game.vignette.position == Vector2.ZERO and game.vignette.texture_filter == CanvasItem.TEXTURE_FILTER_NEAREST, "Mask stays anchored to the internal background with no blur")
	var original_texture: Texture2D = game.vignette.texture
	var original_state: Array = []
	for ghost in game.ghosts:
		original_state.append([ghost.rng.state, ghost.snapshot()])
	for frame in 120:
		game.refresh_views()
	var unchanged: bool = game.vignette.texture == original_texture
	for index in game.ghosts.size():
		unchanged = unchanged and game.ghosts[index].rng.state == original_state[index][0] and game.ghosts[index].snapshot() == original_state[index][1]
	check(unchanged, "View refresh reuses the mask and changes neither ghost's RNG or simulation")
	game.ghosts[0].position = Vector2(88, 280)
	game.ghosts[0].angle = 0
	game.ghosts[0].turn_scale = 1
	game.ghosts[0].bob_height = 0
	game.ghosts[0].talk_text = "みかん、たべる？"
	game.ghosts[1].position = Vector2(680, 350)
	for object in game.objects:
		if object.tag == "water":
			object.position = Vector2(48, 400)
	game.refresh_views()
	game.update_hover(game.views[0].position)
	await rendered_tests(game, settings)
	game.update_hover(Vector2(4, 270))
	check(game.hovered_id.is_empty(), "Background mask cannot become a name-hover target")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = get_root().get_final_transform() * Vector2(4, 270)
	get_root().push_input(click)
	check(game.ghosts[0].target != null and game.ghosts[1].target != null, "Vignette does not consume collection clicks near the room edge")
	game.free()
	finish()


func finish() -> void:
	print("GODOT_VIGNETTE_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
