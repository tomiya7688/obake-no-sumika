extends RefCounted
## Simulation only: no scene, texture, window, file writes, or shared RNG.

const ACTIONS := ["stop", "forward", "turn", "loop", "dash", "water_stop", "seek_talk"]
var id: String
var display_name: String
var native_facing: int
var personality: float
var weights: Dictionary
var rng := RandomNumberGenerator.new()
var position: Vector2
var velocity := Vector2.ZERO
var heading := Vector2.RIGHT
var facing: int = 1
var half_size: Vector2
var bounds: Rect2
var water: Rect2
var action: String = "forward"
var action_timer: float
var elapsed: float = 0.0
var bob_phase: float
var bob_speed: float
var bob_height: float
var turning: bool = false
var turn_elapsed: float = 0.0
var turn_target: int = 1
var turn_scale: float = 1.0
var pending_velocity := Vector2.ZERO
var loop_elapsed: float = 0.0
var loop_duration: float = 7.0
var loop_start := Vector2.ZERO
var loop_radius := Vector2(70, 88)
var loop_travel: float = 150.0
var angle: float = 0.0
var target: Variant = null
var navigation_action: String = "click_move"
var navigation_speed: float = 75
var partner: WeakRef = null
var conversation_available: bool = false
var conversation_controlled: bool = false
var talk_request: bool = false
var talk_cooldown: float
var talk_text: String = ""
var bubble_y_offset: float


func _init(definition: Dictionary, size: Vector2, movement: Rect2, water_zone: Rect2, base_seed: int) -> void:
	id = definition.id
	display_name = definition.display_name
	native_facing = int(definition.native_facing)
	personality = float(definition.personality)
	weights = definition.get("behavior_weights", {}).duplicate()
	half_size = size * 0.5
	bounds = movement.grow_individual(-half_size.x, -half_size.y - 7, -half_size.x, -half_size.y - 7)
	water = water_zone
	position = clamp_position(Vector2(definition.start_position[0], definition.start_position[1]))
	# Stable ID-derived seeds; order and the partner's random draws cannot affect us.
	var seed_value := base_seed & 0x7fffffff
	for index in id.length():
		seed_value = (seed_value * 31 + id.unicode_at(index)) & 0x7fffffff
	rng.seed = seed_value
	heading = random_heading()
	facing = 1 if heading.x >= 0 else -1
	velocity = heading * rng.randf_range(22, 39) * personality
	action_timer = rng.randf_range(1.5, 6)
	bob_phase = rng.randf_range(0, TAU)
	bob_speed = rng.randf_range(0.17, 0.29) * personality
	bob_height = rng.randf_range(3.5, 6.5)
	talk_cooldown = rng.randf_range(3, 9)
	bubble_y_offset = float(definition.get("bubble_y_offset", 0))


func clamp_position(point: Vector2) -> Vector2:
	return Vector2(clampf(point.x, bounds.position.x, bounds.end.x), clampf(point.y, bounds.position.y, bounds.end.y))


func random_heading() -> Vector2:
	var direction: float
	if rng.randf() < 0.78:
		direction = (0.0 if rng.randf() < 0.5 else PI) + rng.randf_range(-0.38, 0.38)
	else:
		direction = rng.randf_range(0, TAU)
	return Vector2.from_angle(direction)


func random_speed() -> float:
	return (rng.randf_range(7, 15) if rng.randf() < 0.28 else rng.randf_range(17, 38)) * personality


func set_velocity(next: Vector2) -> void:
	heading = next.normalized() if next.length_squared() > 0 else heading
	var next_facing := 1 if heading.x >= 0 else -1
	if next_facing != facing:
		turning = true
		turn_elapsed = 0.0
		turn_target = next_facing
		pending_velocity = next
		velocity = Vector2.ZERO
	else:
		velocity = next


func begin_loop() -> bool:
	var room_ahead := (bounds.end.x - position.x) if facing > 0 else (position.x - bounds.position.x)
	var room_above := position.y - bounds.position.y
	if turning or room_ahead < 175 or room_above < 164:
		return false
	loop_elapsed = 0
	loop_duration = rng.randf_range(5.8, 8.2)
	loop_start = position
	loop_travel = minf(rng.randf_range(135, 175), room_ahead - 8)
	loop_radius = Vector2(rng.randf_range(62, 78), minf(rng.randf_range(78, 98), (room_above - 4) * 0.5))
	action = "loop"
	velocity = Vector2.ZERO
	return true


func choose_action() -> void:
	var other: Variant = partner.get_ref() if partner != null else null
	var available: Array[String] = []
	var chances: Array[float] = []
	var total := 0.0
	var defaults := {"stop": 2.0 if personality < 1 else 1.0, "forward": 4.0, "turn": 1.0, "loop": 1.0, "dash": 2.0 if personality < 1 else 3.0, "water_stop": 2.0, "seek_talk": 2.0}
	for candidate in ACTIONS:
		if candidate == "water_stop" and not water.has_point(position):
			continue
		if candidate == "seek_talk" and (not conversation_available or other == null or talk_cooldown > 0 or other.talk_cooldown > 0 or other.conversation_controlled or other.target != null):
			continue
		var weight := float(weights.get(candidate, defaults[candidate]))
		if weight > 0:
			available.append(candidate)
			chances.append(weight)
			total += weight
	if available.is_empty():
		action = "stop"
		action_timer = 2.0
		velocity = Vector2.ZERO
		return
	var roll := rng.randf() * total
	var selected: String = available.back()
	for index in available.size():
		roll -= chances[index]
		if roll <= 0:
			selected = available[index]
			break
	if selected == "loop":
		if begin_loop():
			return
		selected = "forward"
	action = selected
	if action == "seek_talk":
		talk_request = true
		velocity = Vector2.ZERO
		action_timer = 1.0
		return
	if action in ["stop", "water_stop"]:
		velocity = Vector2.ZERO
		if action == "water_stop":
			action_timer = rng.randf_range(2.5, 6.5)
		else:
			action_timer = rng.randf_range(1.1, 5.2) if personality < 1 else rng.randf_range(0.35, 2.8)
		return
	var speed := random_speed()
	if action == "dash":
		speed = rng.randf_range(110, 160) * personality
	if action == "turn":
		heading = random_heading()
	set_velocity(heading * speed)
	action_timer = rng.randf_range(0.65, 1.7) if action == "dash" else rng.randf_range(1.4, 7.5)


func go_to(point: Vector2, travel_action: String = "click_move", speed: float = 75) -> void:
	# Finish the current loop/turn before responding; never cancel half a revolution.
	target = clamp_position(point)
	navigation_action = travel_action
	navigation_speed = speed


func face_toward(direction: int) -> void:
	set_velocity(Vector2(direction, 0))
	velocity = Vector2.ZERO
	pending_velocity = Vector2.ZERO
	angle = 0


func step(delta: float) -> void:
	delta = maxf(delta, 0)
	elapsed += delta
	talk_cooldown = maxf(0, talk_cooldown - delta)
	if action == "loop":
		loop_elapsed += delta
		var progress := clampf(loop_elapsed / loop_duration, 0, 1)
		var orbit := TAU * progress
		position = loop_start + Vector2(facing * (loop_travel * progress + loop_radius.x * sin(orbit)), -loop_radius.y * (1 - cos(orbit)))
		angle = -facing * orbit # Godot positive rotation is clockwise (pygame is opposite).
		if progress >= 1:
			angle = 0
			action = "forward"
			action_timer = rng.randf_range(2.5, 5.5)
			set_velocity(Vector2(facing, 0) * random_speed())
		return
	if turning:
		turn_elapsed += delta
		var progress := minf(turn_elapsed / 0.6, 1.0)
		turn_scale = maxf(0.08, absf(cos(progress * PI)))
		if progress >= 0.5:
			facing = turn_target
		if progress >= 1:
			turning = false
			turn_scale = 1
			velocity = pending_velocity
		return
	if conversation_controlled and target == null:
		velocity = Vector2.ZERO
		angle = 0
		return
	if target != null:
		var distance: Vector2 = target - position
		if distance.length() <= 3:
			position = target
			target = null
			action = "talk_wait" if conversation_controlled else "stop"
			action_timer = 1.0 if conversation_controlled else rng.randf_range(0.8, 1.8)
			velocity = Vector2.ZERO
		else:
			action = navigation_action
			set_velocity(distance.normalized() * minf(navigation_speed * personality, distance.length() / maxf(delta, 0.001)))
	else:
		action_timer -= delta
		if action_timer <= 0:
			choose_action()
	if turning or action == "loop":
		return
	var next := position + velocity * delta
	var reflected := velocity
	if next.x < bounds.position.x or next.x > bounds.end.x:
		reflected.x *= -1
	if next.y < bounds.position.y or next.y > bounds.end.y:
		reflected.y *= -1
	position = clamp_position(next)
	if reflected != velocity:
		set_velocity(reflected)
	angle = deg_to_rad(clampf(velocity.x * 0.08, -5.5, 5.5))


func draw_position() -> Vector2:
	return position + Vector2(0, sin(elapsed * bob_speed * TAU + bob_phase) * bob_height)


func snapshot() -> Dictionary:
	return {"name": id, "x": position.x, "y": position.y, "vx": velocity.x, "vy": velocity.y, "facing": facing, "action": action, "turning": turning, "spin": angle, "target": [target.x, target.y] if target != null else null, "talk": talk_text}
