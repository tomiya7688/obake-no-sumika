extends RefCounted
## Timed terminal/nonterminal event choreography; no scenes, I/O or RNG draws.

const Catalog = preload("res://scripts/event_catalog.gd")
var ghosts: Array
var objects: Dictionary
var distance: float
var id: String = ""
var phase: String = "idle"
var timer: float = 0
var deadline: float = 0
var device: Variant = null


func _init(models: Array, placements: Dictionary, conversation_distance: float) -> void:
	ghosts = models
	objects = placements
	distance = conversation_distance


func ghost_named(name: String) -> Variant:
	for ghost in ghosts:
		if ghost.id == name:
			return ghost
	return null


func motion_finished() -> bool:
	for ghost in ghosts:
		if ghost.action == "loop" or ghost.turning or ghost.target != null:
			return false
	return true


func stop_pair(action: String) -> void:
	for ghost in ghosts:
		ghost.conversation_controlled = true
		ghost.target = null
		ghost.velocity = Vector2.ZERO
		ghost.pending_velocity = Vector2.ZERO
		ghost.angle = 0
		ghost.talk_text = ""
		ghost.action = action


func start(event_id: String, definition: Dictionary) -> bool:
	if phase != "idle" or event_id not in Catalog.IMPLEMENTED or not motion_finished():
		return false
	var tag: String = definition.get("required_tag", "")
	if not tag.is_empty() and not objects.has(tag):
		return false
	if event_id == "game_device" and not objects.has(tag if not tag.is_empty() else "game_device"):
		return false
	id = event_id
	stop_pair("event_wait")
	deadline = 25
	if id == "water_bath":
		var water_tag := tag if not tag.is_empty() else "water"
		var center: Vector2 = objects[water_tag].move_destination() if objects.has(water_tag) else ghosts[0].water.get_center()
		var left = ghosts[0] if ghosts[0].position.x <= ghosts[1].position.x else ghosts[1]
		var right = ghosts[1] if left == ghosts[0] else ghosts[0]
		var gap := maxf(distance, left.half_size.x + right.half_size.x + 36)
		center.x = clampf(center.x, left.bounds.position.x + gap * 0.5, right.bounds.end.x - gap * 0.5)
		center.y = clampf(center.y - 12, maxf(left.bounds.position.y, right.bounds.position.y), minf(left.bounds.end.y, right.bounds.end.y))
		left.go_to(center + Vector2(-gap * 0.5, 0), "event_move", 52)
		right.go_to(center + Vector2(gap * 0.5, 0), "event_move", 52)
		phase = "water_move"
	else:
		device = objects[tag if not tag.is_empty() else "game_device"]
		device.put_away()
		phase = "device_wait"
		timer = 0.8
	return true


func face_pair() -> void:
	for ghost in ghosts:
		var other = ghosts[1] if ghost == ghosts[0] else ghosts[0]
		ghost.face_toward(1 if ghost.position.x < other.position.x else -1)
		ghost.action = "event_turn"


func begin_flee() -> void:
	device.put_away()
	stop_pair("event_wait")
	var left = ghosts[0] if ghosts[0].position.x <= ghosts[1].position.x else ghosts[1]
	var right = ghosts[1] if left == ghosts[0] else ghosts[0]
	left.go_to(Vector2(left.bounds.position.x, left.position.y), "flee", 175)
	right.go_to(Vector2(right.bounds.end.x, right.position.y), "flee", 175)
	deadline = 25
	phase = "flee"


func step(delta: float) -> String:
	if phase == "idle":
		return "failed"
	delta = maxf(0, delta)
	if phase in ["water_move", "water_face", "flee"]:
		deadline -= delta
		if deadline <= 0:
			cancel()
			return "failed"
	else:
		timer -= delta
	match phase:
		"water_move":
			if motion_finished():
				face_pair()
				phase = "water_face"
		"water_face":
			if motion_finished():
				stop_pair("water_bath")
				phase = "water_bath"
				timer = 5
		"water_bath":
			if timer <= 0:
				return "complete"
		"device_wait":
			if timer <= 0:
				var maru = ghost_named("maru")
				device.take_out(maru.position, maru.facing)
				device.glowing = true
				maru.talk_text = "ピカーン"
				phase = "device_flash"
				timer = 1.2
		"device_flash":
			if timer <= 0:
				ghost_named("maru").talk_text = "まぶしいのだーーー"
				phase = "device_maru"
				timer = 2.4
		"device_maru":
			if timer <= 0:
				ghost_named("maru").talk_text = ""
				ghost_named("kadoka").talk_text = "まぶしい"
				phase = "device_kadoka"
				timer = 1.5
		"device_kadoka":
			if timer <= 0:
				begin_flee()
		"flee":
			if motion_finished():
				return "complete"
	return "running"


func cancel() -> void:
	# Only an object owned by this event is cleaned; ordinary take/put is persistent.
	if device != null:
		device.put_away()
	device = null
	id = ""
	phase = "idle"
	timer = 0
	deadline = 0


func snapshot() -> Dictionary:
	return {"id": id, "phase": phase, "timer": maxf(timer, 0)}
