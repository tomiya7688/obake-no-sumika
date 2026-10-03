extends Node2D

const ContentLoader = preload("res://scripts/content_loader.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
const ObjectModel = preload("res://scripts/object_model.gd")
const ConversationController = preload("res://scripts/conversation_controller.gd")
const BubbleView = preload("res://scripts/bubble_view.gd")
const EventView = preload("res://scripts/event_view.gd")
const NameView = preload("res://scripts/name_view.gd")
var room: Dictionary
var ghosts: Array = []
var views: Array[Sprite2D] = []
var objects: Array = []
var object_views: Array[Sprite2D] = []
var object_sizes: Array = []
var event_view := EventView.new()
var world := Node2D.new()
var frame_count: int = 0
var test_frames: int = 0
var screenshot: String = ""
var evaluation: FileAccess
var conversations: Variant = null
var bubbles: Array = []
var name_view := NameView.new()
var hovered_id: String = ""
var pointer_inside_window: bool = true
var pointer_window_position := Vector2.ZERO


func option(name: String, fallback: String = "") -> String:
	var args := OS.get_cmdline_user_args()
	var key := "--" + name
	for index in args.size():
		if args[index].begins_with(key + "="):
			return args[index].substr(key.length() + 1)
		if args[index] == key and index + 1 < args.size():
			return args[index + 1]
	return fallback


func _ready() -> void:
	var loader := ContentLoader.new()
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var data := loader.load_project(option("content-root", root))
	if data.is_empty():
		push_error(loader.error)
		get_tree().quit(1)
		return
	room = data.room
	var raw_bounds: Array = room.movement_bounds
	var bounds := Rect2(raw_bounds[0], raw_bounds[1], raw_bounds[2], raw_bounds[3])
	var raw_water: Array = room.zones.water_rest
	var water := Rect2(raw_water[0], raw_water[1], raw_water[2], raw_water[3])
	world.y_sort_enabled = true
	add_child(world)
	event_view.z_index = 80
	add_child(event_view)
	name_view.z_index = 90 # Below dialogue, above the room and event effects.
	add_child(name_view)
	get_window().mouse_entered.connect(set_pointer_inside.bind(true))
	get_window().mouse_exited.connect(set_pointer_inside.bind(false))
	pointer_window_position = get_viewport().get_final_transform() * get_viewport().get_mouse_position()
	for item in data.objects:
		var model := ObjectModel.new(item.definition)
		var sprite := Sprite2D.new()
		sprite.texture = ImageTexture.create_from_image(item.image)
		sprite.scale = Vector2.ONE * float(item.definition.width) / item.image.get_width()
		# The spring is a floor surface, not a wall that occludes bathing faces.
		sprite.z_index = 0 if model.tag == "water" else 1
		world.add_child(sprite)
		objects.append(model)
		object_views.append(sprite)
		object_sizes.append(sprite.texture.get_size() * sprite.scale)
	var base_seed := int(option("seed", str(Time.get_ticks_usec() ^ int(Time.get_unix_time_from_system()))))
	for item in data.characters:
		var image: Image = item.image
		var height := int(item.definition.display_height)
		image.resize(maxi(1, roundi(float(image.get_width()) * height / image.get_height())), height, Image.INTERPOLATE_LANCZOS)
		var size := Vector2(image.get_width(), image.get_height())
		var model := GhostModel.new(item.definition, size, bounds, water, base_seed)
		var sprite := Sprite2D.new()
		sprite.texture = ImageTexture.create_from_image(image)
		sprite.z_index = 1
		world.add_child(sprite)
		ghosts.append(model)
		views.append(sprite)
		var bubble := BubbleView.new()
		bubble.z_index = 100
		add_child(bubble)
		bubbles.append(bubble)
	conversations = ConversationController.new(ghosts, data.conversations, float(room.conversation_distance), objects, data.events)
	print("CONVERSATION_DECK runnable=", conversations.deck.size(), " skipped=", data.skipped_conversations, " missing_tags=", conversations.unavailable_count)
	test_frames = int(option("test-frames", "0"))
	screenshot = option("screenshot")
	var log_path := option("evaluation-log")
	if not log_path.is_empty():
		evaluation = FileAccess.open(log_path, FileAccess.WRITE)
		if evaluation == null:
			push_error("Cannot open evaluation log: " + log_path)
			get_tree().quit(1)
	refresh_views()
	queue_redraw()


func refresh_views() -> void:
	event_view.set_objects(objects, object_sizes)
	for index in objects.size():
		object_views[index].position = objects[index].position
		object_views[index].visible = objects[index].visible
	for index in ghosts.size():
		var model = ghosts[index]
		views[index].position = model.draw_position()
		views[index].rotation = model.angle
		views[index].flip_h = model.facing != model.native_facing
		views[index].scale = Vector2(model.turn_scale, 1)
		var bubble = bubbles[index]
		bubble.set_message(model.talk_text)
		var point: Vector2 = model.draw_position() + Vector2(-bubble.extent.x * 0.5, -model.half_size.y - bubble.extent.y - 10 + model.bubble_y_offset)
		bubble.position = Vector2(clampf(point.x, 12, 948 - bubble.extent.x), clampf(point.y, 12, 528 - bubble.extent.y))
	update_hover(pointer_world_position(), pointer_inside_window)


func _input(event: InputEvent) -> void:
	if event is InputEventMouse:
		# Keep window pixels so resizing/fullscreen can remap a stationary pointer.
		# Unlike polling the OS pointer, this also supports viewport-forwarded input.
		pointer_window_position = get_viewport().get_final_transform() * event.position
		pointer_inside_window = true


func pointer_world_position() -> Vector2:
	return get_global_transform_with_canvas().affine_inverse() * (get_viewport().get_final_transform().affine_inverse() * pointer_window_position)


func set_pointer_inside(inside: bool) -> void:
	pointer_inside_window = inside
	if inside:
		pointer_window_position = get_viewport().get_final_transform() * get_viewport().get_mouse_position()
	update_hover(pointer_world_position(), inside)


func rendered_bounds(sprite: Sprite2D) -> Rect2:
	var local := sprite.get_rect()
	var result := Rect2(sprite.to_global(local.position), Vector2.ZERO)
	for corner in [local.end, Vector2(local.end.x, local.position.y), Vector2(local.position.x, local.end.y)]:
		result = result.expand(sprite.to_global(corner))
	return result


func update_hover(point: Vector2, inside: bool = true) -> void:
	var selected := -1
	var front_y := -INF
	if inside:
		for index in views.size():
			var sprite := views[index]
			# Undo the same rotation and turn squeeze used for rendering. Viewport
			# stretching/letterboxing is already removed by pointer_world_position.
			if sprite.is_visible_in_tree() and sprite.get_rect().has_point(sprite.to_local(point)) and sprite.global_position.y >= front_y:
				selected = index
				front_y = sprite.global_position.y
	hovered_id = ghosts[selected].id if selected >= 0 else ""
	name_view.set_label(ghosts[selected].display_name if selected >= 0 else "")
	if selected >= 0:
		name_view.place_below(rendered_bounds(views[selected]), Rect2(6, 6, 948, 528))


func _process(delta: float) -> void:
	if ghosts.is_empty():
		return
	var fixed_delta := 1.0 / 60.0 if test_frames > 0 else minf(delta, 0.05)
	for model in ghosts:
		model.step(fixed_delta)
	conversations.step(fixed_delta)
	refresh_views()
	frame_count += 1
	if evaluation != null and frame_count % 10 == 0:
		var snapshots: Array = []
		for model in ghosts:
			snapshots.append(model.snapshot())
		var object_snapshots: Array = []
		for item in objects:
			object_snapshots.append(item.snapshot())
		evaluation.store_line(JSON.stringify({"frame": frame_count, "ghosts": snapshots, "objects": object_snapshots, "conversation": conversations.snapshot()}))
	if test_frames > 0 and frame_count >= test_frames:
		set_process(false)
		if not screenshot.is_empty() and DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
			var result := get_viewport().get_texture().get_image().save_png(screenshot)
			if result != OK:
				push_error("Screenshot failed")
				get_tree().quit(1)
				return
		print("GODOT_SMOKE_OK frames=", frame_count, " ghosts=", ghosts.size())
		get_tree().quit()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			get_tree().quit()
		if event.keycode == KEY_F11 or (event.keycode == KEY_ENTER and event.alt_pressed):
			var full := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if full else DisplayServer.WINDOW_MODE_FULLSCREEN)
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		send_click(pointer_world_position())


func send_click(point: Vector2) -> void:
	if ghosts.size() != 2:
		return
	if conversations.phase != "idle":
		conversations.cancel()
	var left = ghosts[0] if ghosts[0].position.x < ghosts[1].position.x else ghosts[1]
	var right = ghosts[1] if left == ghosts[0] else ghosts[0]
	# Clamp the pair's center, not each destination independently, to keep spacing at walls.
	var center := Vector2(
		clampf(point.x, left.bounds.position.x + 60, right.bounds.end.x - 60),
		clampf(point.y, maxf(left.bounds.position.y, right.bounds.position.y), minf(left.bounds.end.y, right.bounds.end.y))
	)
	left.go_to(center + Vector2(-60, 0))
	right.go_to(center + Vector2(60, 0))


func color_from(raw: Array) -> Color:
	return Color(float(raw[0]) / 255, float(raw[1]) / 255, float(raw[2]) / 255)


func _draw() -> void:
	if room.is_empty():
		return
	var background: Dictionary = room.background
	var gradient: Dictionary = background.gradient
	for y in range(0, 540, int(gradient.step)):
		var color := color_from(gradient.top).lerp(color_from(gradient.bottom), float(y) / 540)
		draw_rect(Rect2(0, y, 960, gradient.step), color)
	for layer in background.polygons:
		var points := PackedVector2Array()
		for point in layer.points:
			points.append(Vector2(point[0], point[1]))
		draw_colored_polygon(points, color_from(layer.color))
