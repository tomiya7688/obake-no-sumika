extends SceneTree

const ShadowView = preload("res://scripts/shadow_view.gd")
var checks: int = 0
var failures: Array[String] = []


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
		check(get_root().get_texture().get_image().save_png(prefix + "-" + suffix + ".png") == OK, "Shadow screenshot saves: " + suffix)


func layer_sample(game: Node2D, shadow: Sprite2D) -> void:
	# A rendered-pixel comparison proves floor visibility and foreground occlusion.
	if DisplayServer.get_name() == "headless":
		return
	game.name_view.visible = false
	await RenderingServer.frame_post_draw
	var with_shadow := get_root().get_texture().get_image()
	game.shadow_layer.visible = false
	await RenderingServer.frame_post_draw
	var without_shadow := get_root().get_texture().get_image()
	game.shadow_layer.visible = true
	var point := get_root().get_final_transform() * shadow.to_global(shadow.get_rect().get_center())
	var pixel := Vector2i(point)
	var changed := with_shadow.get_pixelv(pixel) != without_shadow.get_pixelv(pixel)
	check(changed, "Shadow is actually rendered on top of the opaque spring floor")
	var rock_index := -1
	for index in game.objects.size():
		if game.objects[index].tag == "large_rock":
			rock_index = index
	check(rock_index >= 0, "Source scene includes a foreground rock for depth verification")
	if rock_index < 0:
		return
	var rock = game.objects[rock_index]
	game.ghosts[0].position = rock.position - Vector2(0, game.ghosts[0].half_size.y + 19)
	game.refresh_views()
	game.name_view.visible = false
	await RenderingServer.frame_post_draw
	with_shadow = get_root().get_texture().get_image()
	game.shadow_layer.visible = false
	await RenderingServer.frame_post_draw
	without_shadow = get_root().get_texture().get_image()
	game.shadow_layer.visible = true
	point = get_root().get_final_transform() * shadow.to_global(shadow.get_rect().get_center())
	pixel = Vector2i(point)
	check(with_shadow.get_pixelv(pixel) == without_shadow.get_pixelv(pixel), "Opaque foreground rock renders above the floor shadow")


func run_tests() -> void:
	var pixel_shadow := ShadowView.new(Vector2(64, 64))
	var image := pixel_shadow.texture.get_image()
	check(image.get_size() == Vector2i(37, 5), "Shadow footprint uses source 58% width and 8% height, at least five pixels")
	check(image.get_pixel(0, 0).a == 0, "Corners outside the cross-shaped shadow stay transparent")
	check(is_equal_approx(image.get_pixel(18, 0).a, 46.0 / 255), "Main band preserves source alpha")
	check(is_equal_approx(image.get_pixel(18, 2).a, 34.0 / 255) and is_equal_approx(image.get_pixel(0, 2).a, 34.0 / 255), "Horizontal band overwrites instead of double-blending translucent pixels")
	check(pixel_shadow.texture_filter == CanvasItem.TEXTURE_FILTER_NEAREST and not pixel_shadow.centered, "Pixel shadow is neither blurred nor centered vertically")
	pixel_shadow.free()
	var large := ShadowView.new(Vector2(128, 128))
	check(large.texture.get_size() == Vector2(74, 10), "Shadow size follows the character's display size, not the source PNG resolution")
	large.free()
	var game := (load("res://main.tscn") as PackedScene).instantiate()
	get_root().add_child(game)
	game.set_process(false)
	check(game.shadows.size() == 2 and game.shadows[0].get_parent() == game.shadow_layer, "Scene owns one independent floor shadow for each ghost")
	check(game.shadow_layer.get_index() > game.world.get_index() and game.shadows[0].z_index < game.views[0].z_index, "Floor shadows are after the spring layer and below characters/foreground objects")
	for index in game.ghosts.size():
		var ghost = game.ghosts[index]
		ghost.position = Vector2(300 + index * 340, 350)
		ghost.bob_height = 6
		ghost.bob_phase = 0
		ghost.bob_speed = 1
		ghost.elapsed = 0
		ghost.angle = 0
		ghost.turn_scale = 1
	game.refresh_views()
	for index in game.ghosts.size():
		var ghost = game.ghosts[index]
		check(game.shadows[index].position == ghost.position + Vector2(0, ghost.half_size.y + 19), "Resting shadow stays centered below each display-sized ghost")
	await screenshot(game, "rest")
	var ghost = game.ghosts[0]
	var shadow: Sprite2D = game.shadows[0]
	var initial_shadow := shadow.position
	ghost.elapsed = 0.25
	game.refresh_views()
	check(game.views[0].position.y > ghost.position.y + 5.9 and shadow.position == initial_shadow, "Slow floating changes body height without bouncing the floor shadow")
	var original_texture := shadow.texture
	ghost.angle = PI * 0.5
	ghost.turn_scale = 0.08
	ghost.facing = -ghost.native_facing
	game.refresh_views()
	check(shadow.rotation == 0 and shadow.scale == Vector2.ONE and not shadow.flip_h and shadow.position == initial_shadow, "Shadow never inherits a flip, turn squeeze or body rotation")
	check(shadow.texture == original_texture, "Refresh reuses the texture rather than recreating a bitmap each frame")
	var original_rng: int = ghost.rng.state
	var other_rng: int = game.ghosts[1].rng.state
	var original_snapshot: Dictionary = ghost.snapshot()
	for frame in 120:
		game.refresh_views()
	check(ghost.rng.state == original_rng and game.ghosts[1].rng.state == other_rng and ghost.snapshot() == original_snapshot, "Shadow updates do not consume either character's RNG or alter its simulation")
	game.views[0].visible = false
	game.refresh_views()
	check(not shadow.visible, "Hidden character does not leave a floating orphan shadow")
	game.views[0].visible = true
	for facing in [1, -1]:
		ghost.position = Vector2(280 if facing == 1 else 680, 380)
		ghost.facing = facing
		ghost.turning = false
		ghost.turn_scale = 1
		ghost.angle = 0
		ghost.target = null
		check(ghost.begin_loop(), "A real slow moving loop starts in each direction")
		game.refresh_views()
		var previous := shadow.position
		var start := previous
		var largest_jump := 0.0
		var followed := true
		var photographed := false
		var frame := 0
		while ghost.action == "loop" and frame < 1200:
			ghost.step(1.0 / 60)
			game.refresh_views()
			largest_jump = maxf(largest_jump, shadow.position.distance_to(previous))
			followed = followed and shadow.position.is_equal_approx(ghost.position + Vector2(0, ghost.half_size.y + 19))
			previous = shadow.position
			if not photographed and ghost.loop_elapsed >= ghost.loop_duration * 0.5:
				check(shadow.position.y < start.y - 140, "Shadow follows the loop's actual vertical trajectory, not its starting anchor")
				await screenshot(game, "loop-right" if facing == 1 else "loop-left")
				photographed = true
			frame += 1
		check(followed and ghost.action != "loop" and frame < 1200, "Shadow follows every frame until one full loop finishes")
		check(largest_jump < 4 and shadow.position.x * facing > start.x * facing + 130, "Loop completion has no teleport; shadow exits in the forward direction")
		ghost.step(1.0 / 60)
		game.refresh_views()
		check(shadow.position.distance_to(previous) < 4, "First forward frame after the loop also stays continuous")
	var water_index := -1
	for index in game.objects.size():
		if game.objects[index].tag == "water":
			water_index = index
	check(water_index >= 0 and game.object_views[water_index].z_index == 0, "Spring remains a floor surface")
	if water_index >= 0:
		ghost.position = game.objects[water_index].position - Vector2(0, ghost.half_size.y + 19)
		ghost.angle = 0
		game.refresh_views()
		var water_image: Image = game.object_views[water_index].texture.get_image()
		check(water_image.get_pixelv(water_image.get_size() / 2).a > 0.9, "Spring center is opaque, so depth check cannot pass through a transparent hole")
		await screenshot(game, "water")
		await layer_sample(game, shadow)
	game.update_hover(shadow.position + Vector2(0, 2))
	check(game.hovered_id.is_empty(), "A floor shadow does not become a name-hover target")
	game.free()
	print("GODOT_SHADOW_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
