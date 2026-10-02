extends RefCounted
## Pair choreography and say-only sequencing; simulation code, not rendering.

var ghosts: Array
var deck: Array
var distance: float
var phase: String = "idle"
var seeker: Variant = null
var receiver: Variant = null
var steps: Array = []
var step_index: int = 0
var timer: float = 0.0
var deadline: float = 0.0
var completed_count: int = 0


func _init(models: Array, cards: Array, conversation_distance: float) -> void:
	ghosts = models
	deck = cards
	distance = conversation_distance
	for ghost in ghosts:
		ghost.conversation_available = not deck.is_empty()
		ghost.partner = weakref(ghosts[1] if ghost == ghosts[0] else ghosts[0])


func choose_card(random: RandomNumberGenerator) -> Dictionary:
	var total := 0.0
	for card in deck:
		total += float(card.weight)
	var roll := random.randf() * total
	for card in deck:
		roll -= float(card.weight)
		if roll <= 0:
			return card
	return deck.back() if not deck.is_empty() else {}


func start(initiator: Variant) -> bool:
	if phase != "idle" or deck.is_empty() or initiator not in ghosts:
		return false
	seeker = initiator
	receiver = ghosts[1] if seeker == ghosts[0] else ghosts[0]
	steps = choose_card(seeker.rng).steps.duplicate(true)
	step_index = 0
	deadline = 25.0
	phase = "seek"
	for ghost in ghosts:
		ghost.talk_request = false
		ghost.conversation_available = false
	seeker.conversation_controlled = true
	# Do not modify the receiver's action, movement, target, turn or loop yet.
	seeker.go_to(receiver.position, "seek_talk", 90)
	return true


func lock(ghost: Variant) -> void:
	ghost.conversation_controlled = true
	ghost.target = null
	ghost.talk_text = ""
	if ghost.action != "loop":
		ghost.velocity = Vector2.ZERO
		ghost.pending_velocity = Vector2.ZERO
		ghost.action = "talk_wait"


func motion_finished() -> bool:
	for ghost in ghosts:
		if ghost.action == "loop" or ghost.turning:
			return false
	return true


func align_pair() -> void:
	var left = ghosts[0] if ghosts[0].position.x <= ghosts[1].position.x else ghosts[1]
	var right = ghosts[1] if left == ghosts[0] else ghosts[0]
	var gap := maxf(distance, left.half_size.x + right.half_size.x + 36)
	var x: float = receiver.position.x + (gap * 0.5 if receiver == left else -gap * 0.5)
	x = clampf(x, left.bounds.position.x + gap * 0.5, right.bounds.end.x - gap * 0.5)
	var y := clampf(receiver.position.y, maxf(left.bounds.position.y, right.bounds.position.y), minf(left.bounds.end.y, right.bounds.end.y))
	left.go_to(Vector2(x - gap * 0.5, y), "talk_align", 60)
	right.go_to(Vector2(x + gap * 0.5, y), "talk_align", 60)
	phase = "align"


func show_next_line() -> void:
	for ghost in ghosts:
		ghost.talk_text = ""
		ghost.action = "talk"
	if step_index >= steps.size():
		phase = "afterglow"
		timer = 1.2
		return
	var line: Dictionary = steps[step_index]
	step_index += 1
	for ghost in ghosts:
		if ghost.id == line.speaker:
			ghost.talk_text = line.text
	timer = clampf(1.3 + line.text.length() * 0.055, 1.5, 4.0)
	phase = "talk"


func step(delta: float) -> void:
	if phase == "idle":
		for ghost in ghosts:
			if ghost.talk_request:
				start(ghost)
				break
		return
	if phase in ["seek", "wait_motion", "align", "face"]:
		deadline -= delta
		if deadline <= 0:
			cancel()
			return
	match phase:
		"seek":
			if seeker.position.distance_to(receiver.position) <= distance:
				lock(seeker)
				lock(receiver)
				phase = "wait_motion"
			else:
				seeker.go_to(receiver.position, "seek_talk", 90)
		"wait_motion":
			if motion_finished():
				align_pair()
		"align":
			if ghosts[0].target == null and ghosts[1].target == null and motion_finished():
				for ghost in ghosts:
					var other = ghosts[1] if ghost == ghosts[0] else ghosts[0]
					ghost.face_toward(1 if ghost.position.x < other.position.x else -1)
					ghost.action = "talk_turn"
				phase = "face"
		"face":
			if motion_finished():
				phase = "settle"
				timer = 0.25
		"settle", "talk", "afterglow":
			timer -= delta
			if timer <= 0:
				if phase == "afterglow":
					completed_count += 1
					cancel()
				else:
					show_next_line()


func cancel() -> void:
	for ghost in ghosts:
		ghost.conversation_controlled = false
		ghost.conversation_available = not deck.is_empty()
		ghost.talk_request = false
		ghost.talk_text = ""
		ghost.talk_cooldown = ghost.rng.randf_range(12, 24)
		ghost.target = null
		if ghost.action != "loop":
			ghost.action = "stop"
			ghost.velocity = Vector2.ZERO
			ghost.pending_velocity = Vector2.ZERO
			ghost.action_timer = 1.2
	phase = "idle"
	steps = []
	seeker = null
	receiver = null


func snapshot() -> Dictionary:
	return {"phase": phase, "initiator": seeker.id if seeker != null else null, "step": step_index, "completed": completed_count}
