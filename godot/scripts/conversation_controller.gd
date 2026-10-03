extends RefCounted
## Pair choreography and shared say/move/take/put sequencing; no rendering.

const ScriptedEvents = preload("res://scripts/scripted_events.gd")
const EventCatalog = preload("res://scripts/event_catalog.gd")
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
var objects: Dictionary = {}
var unavailable_count: int = 0
var movers: Array = []
var needs_alignment: bool = false
var meeting_point := Vector2.ZERO
var catalog: Dictionary
var events: RefCounted
var last_event: String = ""


func _init(models: Array, cards: Array, conversation_distance: float, placements: Array = [], event_catalog: Dictionary = {}) -> void:
	ghosts = models
	catalog = event_catalog
	deck = []
	for item in placements:
		if not item.tag.is_empty():
			objects[item.tag] = item
	for card in cards:
		var available := true
		for instruction in card.steps:
			if instruction.type in ["move", "take", "put"] and not objects.has(instruction.tag):
				available = false
			if instruction.type == "event":
				if not catalog.has(instruction.event) or instruction.event not in EventCatalog.IMPLEMENTED:
					available = false
				else:
					var tag: String = catalog[instruction.event].required_tag
					if not tag.is_empty() and not objects.has(tag):
						available = false
					if instruction.event == "game_device" and not objects.has(tag if not tag.is_empty() else "game_device"):
						available = false
		if available:
			deck.append(card)
		else:
			unavailable_count += 1
	distance = conversation_distance
	events = ScriptedEvents.new(ghosts, objects, distance)
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
	needs_alignment = false
	movers = []
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


func align_pair(center: Variant = null) -> void:
	var left = ghosts[0] if ghosts[0].position.x <= ghosts[1].position.x else ghosts[1]
	var right = ghosts[1] if left == ghosts[0] else ghosts[0]
	var gap := maxf(distance, left.half_size.x + right.half_size.x + 36)
	var x: float = receiver.position.x + (gap * 0.5 if receiver == left else -gap * 0.5)
	if center != null:
		x = center.x
	x = clampf(x, left.bounds.position.x + gap * 0.5, right.bounds.end.x - gap * 0.5)
	var y := clampf(receiver.position.y, maxf(left.bounds.position.y, right.bounds.position.y), minf(left.bounds.end.y, right.bounds.end.y))
	if center != null:
		y = clampf(center.y, maxf(left.bounds.position.y, right.bounds.position.y), minf(left.bounds.end.y, right.bounds.end.y))
	left.go_to(Vector2(x - gap * 0.5, y), "talk_align", 60)
	right.go_to(Vector2(x + gap * 0.5, y), "talk_align", 60)
	phase = "align"


func advance_sequence() -> void:
	for ghost in ghosts:
		ghost.talk_text = ""
		ghost.action = "talk"
	# A move is allowed to involve only one actor. Rejoin only before speaking.
	if needs_alignment and (step_index >= steps.size() or steps[step_index].type in ["say", "event"]):
		needs_alignment = false
		deadline = 25.0
		align_pair(meeting_point)
		return
	if step_index >= steps.size():
		phase = "afterglow"
		timer = 1.2
		return
	var instruction: Dictionary = steps[step_index]
	step_index += 1
	if instruction.type == "event":
		if events.start(instruction.event, catalog[instruction.event]):
			phase = "event"
		else:
			cancel()
		return
	if instruction.type in ["move", "take", "put"]:
		var item = objects[instruction.tag]
		var actors: Array = [seeker, receiver] if instruction.actor == "both" else []
		if actors.is_empty():
			for ghost in ghosts:
				if ghost.id == instruction.actor:
					actors.append(ghost)
		for ghost in ghosts:
			lock(ghost)
			ghost.action = "sequence_wait"
		if instruction.type == "move":
			movers = actors
			var destination: Vector2 = item.move_destination()
			for index in actors.size():
				var offset := (index * 2 - (actors.size() - 1)) * 54
				actors[index].go_to(destination + Vector2(offset, -38), "sequence_move", 75)
			needs_alignment = true
			deadline = 25.0
			phase = "object_move"
		else:
			if instruction.type == "take":
				# As in Python, `both` takes out once using the initiator's side.
				item.take_out(actors[0].position, actors[0].facing)
			else:
				item.put_away()
			phase = "object_pause"
			timer = 0.8
		return
	for ghost in ghosts:
		if ghost.id == instruction.speaker:
			ghost.talk_text = instruction.text
	timer = clampf(1.3 + instruction.text.length() * 0.055, 1.5, 4.0)
	phase = "talk"


func step(delta: float) -> void:
	if phase == "idle":
		for ghost in ghosts:
			if ghost.talk_request:
				start(ghost)
				break
		return
	if phase == "event":
		var status: String = events.step(delta)
		if status == "complete":
			last_event = events.id
			var terminal: bool = catalog[events.id].terminal
			events.cancel()
			if terminal:
				completed_count += 1
				cancel()
			else:
				needs_alignment = true
				meeting_point = (ghosts[0].position + ghosts[1].position) * 0.5
				advance_sequence()
		elif status == "failed":
			cancel()
		return
	if phase in ["seek", "wait_motion", "align", "face", "object_move"]:
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
		"object_move":
			var arrived := motion_finished()
			for ghost in movers:
				arrived = arrived and ghost.target == null
			if arrived:
				meeting_point = Vector2.ZERO
				for ghost in movers:
					meeting_point += ghost.position
				meeting_point /= movers.size()
				movers = []
				advance_sequence()
		"settle", "talk", "object_pause", "afterglow":
			timer -= delta
			if timer <= 0:
				if phase == "afterglow":
					completed_count += 1
					cancel()
				else:
					advance_sequence()


func cancel() -> void:
	events.cancel()
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
	movers = []
	needs_alignment = false
	seeker = null
	receiver = null


func snapshot() -> Dictionary:
	var actor_ids: Array = []
	for ghost in movers:
		actor_ids.append(ghost.id)
	return {"phase": phase, "initiator": seeker.id if seeker != null else null, "step": step_index, "completed": completed_count, "movers": actor_ids, "event": events.snapshot(), "last_event": last_event}
