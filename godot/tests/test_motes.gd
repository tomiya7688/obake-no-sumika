extends SceneTree

const MoteField = preload("res://scripts/mote_field.gd")
const ContentLoader = preload("res://scripts/content_loader.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
var checks: int = 0
var failures: Array[String] = []


class InvalidMoteLoader:
	extends ContentLoader

	func read_json(raw: Variant) -> Dictionary:
		var data := super.read_json(raw)
		if data.has("motes"):
			data = data.duplicate(true)
			data.motes.count = -1
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
		check(get_root().get_texture().get_image().save_png(prefix + "-" + suffix + ".png") == OK, "Mote screenshot saves: " + suffix)


func pixel_at(image: Image, game: Node2D, point: Vector2) -> Color:
	var pixel := Vector2i(get_root().get_stretch_transform() * game.get_global_transform_with_canvas() * point)
	return image.get_pixelv(pixel)


func particle_at(point: Vector2, radius: int = 2) -> Dictionary:
	return {"position": point, "radius": radius, "alpha": 220, "speed": 0.0, "phase": 0.0}


func captured_frame(game: Node2D, motes_visible: bool) -> Image:
	game.mote_view.visible = motes_visible
	# Let pending window/input changes settle, then pin the hover for this frame.
	# Mouse-enter/motion events during resize must not change the UI between samples.
	await process_frame
	game.refresh_views()
	game.update_hover(game.views[0].position)
	await RenderingServer.frame_post_draw
	return get_root().get_texture().get_image()


func rendered_comparison(game: Node2D, label: String) -> void:
	game.refresh_views()
	game.update_hover(game.views[0].position)
	check(game.name_view.visible and game.bubbles[0].visible, label + ": foreground UI is visible")
	var water_point := Vector2.ZERO
	var rock_point := Vector2.ZERO
	for object in game.objects:
		if object.tag == "water":
			water_point = object.position
		if object.tag == "large_rock":
			rock_point = object.position
	var foreground: Array[Vector2] = [game.views[0].position, rock_point, game.bubbles[0].position + Vector2(15, 15), game.name_view.position + Vector2(3, 3)]
	game.motes.particles.clear()
	game.motes.particles.append(particle_at(water_point))
	for point in foreground:
		game.motes.particles.append(particle_at(point))
	game.mote_view.queue_redraw()
	var enabled := await captured_frame(game, true)
	var disabled := await captured_frame(game, false)
	game.mote_view.visible = true
	check(pixel_at(enabled, game, water_point) != pixel_at(disabled, game, water_point), label + ": mote actually draws above the water floor")
	check(pixel_at(enabled, game, water_point + Vector2(3, 0)) == pixel_at(disabled, game, water_point + Vector2(3, 0)), label + ": radius two draws a four-pixel square, not a halo")
	for index in foreground.size():
		var point := foreground[index]
		var same := pixel_at(enabled, game, point) == pixel_at(disabled, game, point)
		check(same, label + ": foreground " + str(index) + " covers the mote")


func rendered_tests(game: Node2D) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var source_particles: Array[Dictionary] = game.motes.snapshot()
	await screenshot(game, "start")
	game.motes.step(4.0)
	game.refresh_views()
	game.update_hover(game.views[0].position)
	await screenshot(game, "drift")
	var drift_particles: Array[Dictionary] = game.motes.snapshot()
	await rendered_comparison(game, "960x540")
	var original_size := get_root().size
	get_root().size = Vector2i(1280, 1024)
	await process_frame
	await rendered_comparison(game, "Letterboxed window")
	game.motes.particles = drift_particles.duplicate(true)
	game.mote_view.queue_redraw()
	await screenshot(game, "letterbox")
	get_root().size = original_size
	await process_frame
	var toggle := InputEventKey.new()
	toggle.keycode = KEY_F11
	toggle.pressed = true
	get_root().push_input(toggle)
	await process_frame
	await RenderingServer.frame_post_draw
	check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN, "F11 enters fullscreen with motes")
	await rendered_comparison(game, "Fullscreen")
	game.motes.particles = drift_particles.duplicate(true)
	game.mote_view.queue_redraw()
	await screenshot(game, "fullscreen")
	get_root().push_input(toggle)
	await process_frame
	await RenderingServer.frame_post_draw
	check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED, "F11 returns to windowed mode with motes")
	game.motes.particles = source_particles
	game.mote_view.queue_redraw()


func test_settings(settings: Dictionary) -> void:
	check(MoteField.validate(settings, 540).is_empty(), "Shared mote settings are valid")
	for bad in [null, [], "dust"]:
		check(not MoteField.validate(bad, 540).is_empty(), "Non-object mote settings are rejected")
	var bad_fields := {
		"count": [null, true, -1, 1001, 1.5, NAN],
		"top": [null, true, -1, 541, INF],
		"drift_speed": [null, true, -1, 101, NAN],
		"drift_amount": [null, false, -1, 101, INF],
		"x_range": [[], [1, 1], [2, 1], [-10001, 0], [0, INF], [false, 1]],
		"y_range": [null, [1], [2, 1], [0, 10001]],
		"reset_y_range": [null, [3, 3], [NAN, 500]],
		"speed_range": [[-1, 1], [0, 0], [0, INF], [0, "slow"]],
		"radii": [null, [], [0], [101], [1.5], [true]],
		"alpha_range": [[], [0, 256], [-1, 5], [5, 4], [true, 5], [1.5, 5]],
		"color": [null, [0, 0], [0, 0, 256], [-1, 0, 0], [0, true, 0], [0, 0, NAN]]
	}
	for field in bad_fields:
		for bad in bad_fields[field]:
			var invalid := settings.duplicate(true)
			invalid[field] = bad
			check(not MoteField.validate(invalid, 540).is_empty(), "Invalid mote setting is rejected: " + field)
	var maximum := settings.duplicate(true)
	maximum.count = 1000
	maximum.alpha_range = [255, 255]
	maximum.radii = [100]
	check(MoteField.validate(maximum, 540).is_empty() and MoteField.new(maximum, 12345).particles.size() == 1000, "Valid upper count, equal alpha endpoints and maximum radius are supported")
	var zero := settings.duplicate(true)
	zero.count = 0
	zero.alpha_range = [0, 0]
	check(MoteField.validate(zero, 540).is_empty() and MoteField.new(zero, 12345).particles.is_empty(), "Count zero disables motes without invalidating the room")


func test_simulation(data: Dictionary) -> void:
	var settings: Dictionary = data.room.motes
	var one := MoteField.new(settings, 12345)
	var two := MoteField.new(settings, 12345)
	check(one.snapshot() == two.snapshot(), "Same seed produces the same initial particles")
	check(one.snapshot() != MoteField.new(settings, 54321).snapshot(), "Different seed changes ambient positions")
	var in_ranges := true
	var valid_radii: Array[int] = []
	for radius in settings.radii:
		valid_radii.append(int(radius))
	for particle in one.particles:
		in_ranges = in_ranges and particle.position.x >= settings.x_range[0] and particle.position.x <= settings.x_range[1] and particle.position.y >= settings.y_range[0] and particle.position.y <= settings.y_range[1] and particle.speed >= settings.speed_range[0] and particle.speed <= settings.speed_range[1] and particle.radius in valid_radii and particle.alpha >= settings.alpha_range[0] and particle.alpha <= settings.alpha_range[1]
	check(one.particles.size() == int(settings.count) and in_ranges, "Count, initial ranges, speed, weighted radii and alpha use shared settings")
	var independent_settings := settings.duplicate(true)
	var isolated := MoteField.new(independent_settings, 1)
	independent_settings.radii[0] = 99
	check(isolated.settings.radii[0] == 1, "Simulation owns its settings without modifying or following shared dictionaries")
	var particle: Dictionary = one.particles[0]
	particle.position = Vector2(300, 300)
	particle.speed = 4.0
	particle.phase = PI / 2
	var original_rng: int = one.rng.state
	one.step(0.5)
	check(is_equal_approx(particle.position.y, 298) and is_equal_approx(particle.position.x, 300 + sin(0.5 * settings.drift_speed + PI / 2) * settings.drift_amount * 0.5), "Rise and sideways drift match the time-based source formula")
	check(one.rng.state == original_rng, "Ordinary motion consumes no random draws")
	particle.position.y = settings.top
	particle.speed = 0
	one.step(0.1)
	check(is_equal_approx(particle.position.y, settings.top), "Particle exactly at the top does not respawn")
	var appearance := [particle.speed, particle.phase, particle.radius, particle.alpha]
	particle.position.y = settings.top - 1
	one.step(0.1)
	check(particle.position.y >= settings.reset_y_range[0] and particle.position.y <= settings.reset_y_range[1] and particle.position.x >= settings.x_range[0] and particle.position.x <= settings.x_range[1], "Crossing the top respawns only position in shared reset ranges")
	check([particle.speed, particle.phase, particle.radius, particle.alpha] == appearance, "Respawn retains speed, phase, radius and opacity")
	var before := one.snapshot()
	var before_elapsed := one.elapsed
	for bad_delta in [0.0, -1.0, NAN, INF]:
		one.step(bad_delta)
	check(one.snapshot() == before and one.elapsed == before_elapsed, "Zero or invalid delta cannot corrupt ambient motion")
	var a := MoteField.new(settings, 12345)
	var b := MoteField.new(settings, 12345)
	var ghost_a := GhostModel.new(data.characters[0].definition, Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345)
	var ghost_b := GhostModel.new(data.characters[0].definition, Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345)
	for frame in 6000:
		a.step(1.0 / 60)
		b.step(1.0 / 60)
		# Extra scenery draws/respawns must not affect either character stream.
		one.rng.randf()
		one.step(1.0 / 60)
		ghost_a.step(1.0 / 60)
		ghost_b.step(1.0 / 60)
	check(a.snapshot() == b.snapshot() and a.particles.size() == int(settings.count), "100 seconds of rises/respawns stays deterministic with a stable count")
	check(ghost_a.snapshot() == ghost_b.snapshot(), "Extra ambient draws do not change character simulation")
	var empty := settings.duplicate(true)
	empty.count = 0
	var no_motes := MoteField.new(empty, 12345)
	var empty_rng: int = no_motes.rng.state
	no_motes.step(600.0)
	check(no_motes.particles.is_empty() and no_motes.rng.state == empty_rng, "Disabled field remains empty and consumes no RNG")


func run_tests() -> void:
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var loader := ContentLoader.new()
	var data := loader.load_project(root)
	check(not data.is_empty(), "Shared source project loads: " + loader.error)
	if data.is_empty():
		finish()
		return
	test_settings(data.room.motes)
	var invalid_loader := InvalidMoteLoader.new()
	check(invalid_loader.load_project(root).is_empty() and "motes.count" in invalid_loader.error, "Real load path rejects invalid ambient settings before rendering")
	test_simulation(data)
	var game := (load("res://main.tscn") as PackedScene).instantiate()
	get_root().add_child(game)
	game.set_process(false)
	check(game.motes.particles.size() == int(data.room.motes.count) and game.mote_view.field == game.motes, "Scene binds the shared particle count to one ambient view")
	check(game.mote_view.z_index == 0 and game.mote_view.get_index() > game.shadow_layer.get_index() and game.views[0].z_index == 1, "Ambient squares are above the floor and below foreground ghosts")
	var old_motes: Array[Dictionary] = game.motes.snapshot()
	var old_rng: int = game.motes.rng.state
	var old_ghosts: Array = []
	for ghost in game.ghosts:
		old_ghosts.append([ghost.rng.state, ghost.snapshot()])
	for frame in 120:
		game.refresh_views()
	var unchanged: bool = game.motes.snapshot() == old_motes and game.motes.rng.state == old_rng
	for index in game.ghosts.size():
		unchanged = unchanged and [game.ghosts[index].rng.state, game.ghosts[index].snapshot()] == old_ghosts[index]
	check(unchanged, "Rendering refresh consumes no scenery/ghost RNG and advances no simulation")
	var elapsed: float = game.motes.elapsed
	game._process(1.0 / 60)
	check(is_equal_approx(game.motes.elapsed, elapsed + 1.0 / 60) and game.motes.snapshot() != old_motes, "Live process advances ambient motion with the game's delta")
	game.ghosts[0].position = Vector2(320, 300)
	game.ghosts[0].bob_height = 0
	game.ghosts[0].angle = 0
	game.ghosts[0].turn_scale = 1
	game.ghosts[0].talk_text = "みかん、たべる？"
	game.refresh_views()
	game.update_hover(game.views[0].position)
	await rendered_tests(game)
	game.update_hover(Vector2(100, 100))
	check(game.hovered_id.is_empty(), "A mote or its view cannot become a name-hover target")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = get_root().get_final_transform() * Vector2(480, 270)
	get_root().push_input(click)
	check(game.ghosts[0].target != null and game.ghosts[1].target != null, "Ambient view does not consume collection input")
	game.free()
	finish()


func finish() -> void:
	print("GODOT_MOTE_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
