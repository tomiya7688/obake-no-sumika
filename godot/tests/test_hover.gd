extends SceneTree

var checks: int = 0
var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("run_tests")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func push_mouse(game: Node2D, point: Vector2) -> void:
	var motion := InputEventMouseMotion.new()
	motion.position = get_root().get_final_transform() * point
	get_root().push_input(motion)
	game.refresh_views()


func screenshot(game: Node2D, suffix: String) -> void:
	var prefix: String = game.option("screenshot-prefix")
	if not prefix.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(prefix + "-" + suffix + ".png") == OK, "Hover screenshot saves: " + suffix)


func run_tests() -> void:
	var game := (load("res://main.tscn") as PackedScene).instantiate()
	get_root().add_child(game)
	game.set_process(false)
	for index in game.ghosts.size():
		var ghost = game.ghosts[index]
		ghost.position = Vector2(320 + index * 300, 300)
		ghost.bob_height = 0
		ghost.angle = 0
		ghost.turn_scale = 1
	game.refresh_views()
	game.update_hover(Vector2(20, 20))
	check(not game.name_view.visible and game.hovered_id.is_empty(), "No permanent name labels over empty cave")
	for index in game.ghosts.size():
		var ghost = game.ghosts[index]
		game.update_hover(game.views[index].position)
		check(game.name_view.visible and game.name_view.displayed_name == ghost.display_name and game.hovered_id == ghost.id, "Each shared character display name appears on hover")
		check(game.name_view.position.y >= game.rendered_bounds(game.views[index]).end.y + 5.9, "Name sits below the rendered ghost")
		check(game.name_view.rotation == 0 and game.name_view.scale == Vector2.ONE and game.name_view.z_index < game.bubbles[index].z_index, "Name stays upright and below speech layer")
		await screenshot(game, ghost.id)
	game.ghosts[0].display_name = "かどかさん"
	game.update_hover(game.views[0].position)
	check(game.name_view.displayed_name == "かどかさん", "Label uses the model's shared-data display name, not a hardcoded ID")
	game.ghosts[0].display_name = "かどか"
	game.update_hover(Vector2(20, 20))
	check(not game.name_view.visible and game.name_view.displayed_name.is_empty(), "Leaving both ghosts removes the name immediately")
	game.views[0].visible = false
	game.update_hover(game.views[0].position)
	check(not game.name_view.visible, "Hidden sprites are not pointer targets")
	game.views[0].visible = true
	game.ghosts[0].turn_scale = 0.08
	game.refresh_views()
	game.update_hover(game.views[0].position + Vector2(12, 0))
	check(not game.name_view.visible, "Turn squeeze also narrows the hover target")
	game.update_hover(game.views[0].position)
	check(game.hovered_id == "kadoka", "A squeezed ghost can still be hovered at its center")
	game.ghosts[0].turn_scale = 1
	game.ghosts[0].facing = 1
	game.ghosts[0].turning = false
	check(game.ghosts[0].begin_loop(), "Hover test starts a real moving loop")
	game.ghosts[0].step(game.ghosts[0].loop_duration * 0.25)
	game.refresh_views()
	var rotated_point: Vector2 = game.views[0].to_global(Vector2(0, 20))
	game.update_hover(rotated_point)
	check(game.hovered_id == "kadoka" and is_equal_approx(game.views[0].rotation, -PI * 0.5), "Hover follows actual loop position and rotation")
	var outside: Vector2 = game.views[0].to_global(game.views[0].get_rect().end + Vector2.ONE)
	game.update_hover(outside)
	check(not game.name_view.visible, "Outside rotated render rectangle is not hovered")
	for index in game.ghosts.size():
		game.ghosts[index].angle = 0
		game.ghosts[index].position = Vector2(400, 300 + index * 10)
	game.refresh_views()
	game.update_hover(Vector2(400, 305))
	check(game.hovered_id == "maru", "Overlapping ghosts show only the frontmost Y-sorted name")
	game.ghosts[0].position.y = 320
	game.refresh_views()
	game.update_hover(Vector2(400, 315))
	check(game.hovered_id == "kadoka", "Overlap selection follows visual order, not character list order")
	game.ghosts[0].position.y = 310
	game.refresh_views()
	game.update_hover(Vector2(400, 310))
	check(game.hovered_id == "maru", "Equal-Y overlap uses later sprite insertion order")
	for corner in [Vector2(0, 0), Vector2(960, 0), Vector2(0, 540), Vector2(960, 540)]:
		game.ghosts[0].position = corner
		game.refresh_views()
		game.update_hover(corner)
		var label_bounds := Rect2(game.name_view.position, game.name_view.extent)
		check(game.hovered_id == "kadoka" and Rect2(6, 6, 948, 528).encloses(label_bounds), "Name remains inside the internal screen at each corner")
	game.ghosts[0].position = Vector2(320, 300)
	game.ghosts[1].position = Vector2(620, 300)
	game.ghosts[0].talk_text = "みかん、たべる？"
	var original_rng: int = game.ghosts[0].rng.state
	var original_snapshot: Dictionary = game.ghosts[0].snapshot()
	game.refresh_views()
	for draw in 120:
		game.update_hover(game.views[0].position)
	check(game.ghosts[0].rng.state == original_rng and game.ghosts[0].snapshot() == original_snapshot and game.bubbles[0].visible, "Hover neither draws RNG nor changes movement or speech")
	await screenshot(game, "conversation")
	get_root().mouse_exited.emit()
	game.refresh_views()
	check(not game.name_view.visible and game.hovered_id.is_empty(), "Window mouse exit cannot leave a stale name")
	get_root().mouse_entered.emit()
	push_mouse(game, game.views[0].position)
	check(game.hovered_id == "kadoka", "Viewport input reaches the live stationary-cursor hover path")
	game.ghosts[0].position.x = 220
	game.refresh_views()
	check(not game.name_view.visible, "A ghost moving away from a stationary mouse clears its label")
	var original_size := get_root().size
	var saved_window_pointer: Vector2 = game.pointer_window_position
	get_root().size = Vector2i(1280, 1024)
	await process_frame
	game.refresh_views()
	check(game.pointer_window_position == saved_window_pointer and game.pointer_world_position().is_equal_approx(get_root().get_final_transform().affine_inverse() * saved_window_pointer), "Resizing remaps a stationary window-pixel pointer without waiting for mouse motion")
	game.ghosts[0].position = Vector2(320, 300)
	game.refresh_views()
	push_mouse(game, game.views[0].position)
	check(game.hovered_id == "kadoka" and game.name_view.position.x < 960, "Stretched letterboxed input maps back to internal game coordinates")
	var black_bar_mouse := InputEventMouseMotion.new()
	black_bar_mouse.position = Vector2(640, 10)
	get_root().push_input(black_bar_mouse)
	game.refresh_views()
	check(not game.name_view.visible, "Pointer in letterbox bars does not hover a ghost")
	push_mouse(game, game.views[1].position)
	check(game.hovered_id == "maru", "Both characters hover correctly in a non-16:9 window")
	await screenshot(game, "letterbox")
	get_root().size = original_size
	await process_frame
	if DisplayServer.get_name() != "headless":
		var toggle := InputEventKey.new()
		toggle.keycode = KEY_F11
		toggle.pressed = true
		get_root().push_input(toggle)
		await process_frame
		await RenderingServer.frame_post_draw
		push_mouse(game, game.views[0].position)
		check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN and game.hovered_id == "kadoka", "F11 fullscreen keeps actual pointer input on the ghost")
		await screenshot(game, "fullscreen")
		get_root().push_input(toggle)
		await process_frame
		await RenderingServer.frame_post_draw
		push_mouse(game, game.views[1].position)
		check(DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED and game.hovered_id == "maru", "Returning to windowed mode preserves hover coordinates")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = get_root().get_final_transform() * game.views[0].position
	get_root().push_input(click)
	check(game.ghosts[0].target != null and game.ghosts[1].target != null, "Name overlay does not consume click collection")
	check(game.ghosts[0].target == game.views[0].position + Vector2(-60, 0) and game.ghosts[1].target == game.views[0].position + Vector2(60, 0), "Click and hover use the same viewport-mapped pointer position")
	game.free()
	print("GODOT_HOVER_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
