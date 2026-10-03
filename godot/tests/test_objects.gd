extends SceneTree

const ContentLoader = preload("res://scripts/content_loader.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
const ObjectModel = preload("res://scripts/object_model.gd")
const Deck = preload("res://scripts/conversation_deck.gd")
const Controller = preload("res://scripts/conversation_controller.gd")
var checks: int = 0
var failures: Array[String] = []
var definitions: Array


func _initialize() -> void:
	call_deferred("run_tests")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func make_pair() -> Array:
	var pair: Array = []
	for definition in definitions:
		var ghost := GhostModel.new(definition, Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345)
		ghost.position = Vector2(340 + pair.size() * 120, 300)
		ghost.facing = 1 if pair.is_empty() else -1
		ghost.turning = false
		ghost.velocity = Vector2.ZERO
		ghost.action = "stop"
		ghost.action_timer = 100
		pair.append(ghost)
	return pair


func advance(pair: Array, controller: RefCounted, delta: float = 1.0 / 60) -> void:
	for ghost in pair:
		ghost.step(delta)
	controller.step(delta)


func until_phase(pair: Array, controller: RefCounted, phase: String, frames: int = 1800) -> bool:
	for frame in frames:
		advance(pair, controller)
		if controller.phase == phase:
			return true
	return false


func run_tests() -> void:
	var loader := ContentLoader.new()
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var data := loader.load_project(root)
	check(not data.is_empty(), "Shared objects load: " + loader.error)
	if data.is_empty():
		finish()
		return
	definitions = [data.characters[0].definition, data.characters[1].definition]
	var raw: Dictionary = data.objects.back().definition.duplicate(true)
	check(loader.validate_placements([raw]), "Valid hidden placement is accepted")
	for changes in [{"visible": "false"}, {"tag": 3}, {"id": ""}, {"x": NAN}]:
		var invalid := raw.duplicate(true)
		invalid.merge(changes, true)
		check(not loader.validate_placements([invalid]), "Invalid placement is rejected: " + str(changes))
	var duplicate := raw.duplicate(true)
	duplicate.id = "different_id"
	check(not loader.validate_placements([raw, duplicate]), "Duplicate tags cannot ambiguously select an object")
	duplicate.tag = "other_tag"
	duplicate.id = raw.id
	check(not loader.validate_placements([raw, duplicate]), "Duplicate placement IDs are rejected")
	var untagged := raw.duplicate(true)
	untagged.erase("tag")
	check(loader.validate_placements([untagged]), "Existing untagged objects remain supported")
	var device := ObjectModel.new(raw)
	var home := device.home_position
	check(not device.visible and device.move_destination() == home, "Hidden object uses its original placement for move")
	device.take_out(Vector2(600, 300), -1)
	check(device.visible and device.position == Vector2(558, 318) and device.home_position == home, "Take shows the object on the actor's facing side without changing home")
	check(device.move_destination() == device.position, "Visible object uses its current position for move")
	device.put_away()
	check(not device.visible and device.move_destination() == home, "Put hides it and subsequent move uses home again")
	var steps := [
		{"type": "move", "actor": "maru", "tag": "game_device"},
		{"type": "take", "actor": "maru", "tag": "game_device"},
		{"type": "say", "speaker": "maru", "text": "これ拾ったのだ"},
		{"type": "say", "speaker": "kadoka", "text": "なに、これ"},
		{"type": "put", "actor": "both", "tag": "game_device"},
		{"type": "say", "speaker": "kadoka", "text": "しまったね"},
	]
	var parsed := Deck.parse([{"weight": 3, "steps": steps}])
	check(parsed.error.is_empty() and parsed.cards.size() == 1 and parsed.cards[0].steps == steps, "Shared move/take/put and multiple say steps are preserved")
	var normalized := Deck.parse([{"steps": [{"type": "take", "tag": "  大きい 岩  "}]}])
	check(normalized.error.is_empty() and normalized.cards[0].steps[0].tag == "大きい_岩" and normalized.cards[0].steps[0].actor == "kadoka", "Tags and omitted actor follow shared normalization/default")
	for instruction in [
		{"type": "move", "actor": "human", "tag": "water"},
		{"type": "take", "actor": "both", "tag": "  "},
		{"type": "put", "actor": "maru", "tag": 5},
	]:
		check(not Deck.parse([{"steps": [instruction]}]).error.is_empty(), "Malformed object instruction is rejected")
	var mixed := Deck.parse([{"steps": steps + [{"type": "event", "event": "game_device"}]}])
	check(mixed.cards.is_empty() and mixed.skipped == 1, "Unported event still excludes the whole card, including object actions")
	var pair := make_pair()
	var missing := Controller.new(pair, parsed.cards, 145)
	var rng_before: int = pair[0].rng.state
	check(missing.deck.is_empty() and missing.unavailable_count == 1 and not missing.start(pair[0]) and pair[0].rng.state == rng_before and not pair[0].conversation_available, "Missing tag excludes the whole card without a partial execution or RNG draw")
	var eligible := Controller.new(pair, parsed.cards + [{"weight": 1, "steps": [{"type": "say", "speaker": "kadoka", "text": "こんにちは"}]}], 145)
	check(eligible.deck.size() == 1 and eligible.unavailable_count == 1 and pair[0].conversation_available and eligible.choose_card(pair[0].rng).steps[0].type == "say", "Unavailable object card does not suppress remaining eligible dialogue")
	var controller := Controller.new(pair, parsed.cards, 145, [device])
	check(controller.start(pair[0]) and until_phase(pair, controller, "object_move"), "Tagged sequence starts after normal approach/alignment")
	var waiting_position: Vector2 = pair[0].position
	check(pair[0].target == null and pair[1].target == home + Vector2(0, -38) and controller.snapshot().movers == ["maru"], "Single-actor move targets the hidden object's home; other actor waits")
	var waiting_still := true
	var silent := true
	for frame in 1800:
		advance(pair, controller)
		waiting_still = waiting_still and pair[0].position == waiting_position
		silent = silent and pair[0].talk_text.is_empty() and pair[1].talk_text.is_empty()
		if controller.phase != "object_move":
			break
	check(waiting_still and silent and controller.phase == "object_pause", "Move completes before take or speech and only the selected actor moves")
	check(device.visible and device.position == Vector2(roundf(pair[1].position.x + pair[1].facing * 42), roundf(pair[1].position.y + 18)), "Take executes beside the selected actor after arrival")
	for frame in 24:
		advance(pair, controller)
	check(controller.phase == "object_pause" and controller.step_index == 2, "Object action has a visible pause before advancing")
	check(until_phase(pair, controller, "talk"), "Re-alignment finishes before next speech")
	var stable_pose := true
	var seen_lines: Array[String] = []
	var seen_put := false
	for frame in 1800:
		advance(pair, controller)
		for ghost in pair:
			if not ghost.talk_text.is_empty():
				var other = pair[1] if ghost == pair[0] else pair[0]
				stable_pose = stable_pose and not ghost.turning and is_zero_approx(ghost.angle) and ghost.velocity == Vector2.ZERO and absf(pair[0].position.y - pair[1].position.y) < 0.01 and absf(pair[0].position.x - pair[1].position.x) >= 144.9 and (other.position.x - ghost.position.x) * ghost.facing > 0
				if seen_lines.is_empty() or seen_lines.back() != ghost.talk_text:
					seen_lines.append(ghost.talk_text)
		if controller.phase == "object_pause" and not device.visible:
			seen_put = true
		if controller.completed_count == 1:
			break
	check(stable_pose and seen_lines == ["これ拾ったのだ", "なに、これ", "しまったね"], "After move, all dialogue is stopped, horizontal, facing and in JSON order")
	check(seen_put and not device.visible and controller.phase == "idle" and not pair[1].conversation_controlled, "Put then later say complete and both return to AI")
	pair = make_pair()
	var both_cards := Deck.parse([{"steps": [{"type": "move", "actor": "both", "tag": "game_device"}, {"type": "take", "actor": "both", "tag": "game_device"}]}])
	controller = Controller.new(pair, both_cards.cards, 145, [device])
	controller.start(pair[1])
	check(until_phase(pair, controller, "object_move") and pair[0].target != null and pair[1].target != null and is_equal_approx(absf(pair[0].target.x - pair[1].target.x), 108), "Both moves use two separated destinations")
	check(until_phase(pair, controller, "object_pause") and device.position.x == roundf(pair[1].position.x + pair[1].facing * 42), "Both take places one object using the initiator, matching Python")
	controller.cancel()
	check(controller.phase == "idle" and controller.movers.is_empty() and pair[0].target == null and pair[1].target == null and device.visible, "Cancel releases navigation; already applied object changes are not rolled back")
	pair = make_pair()
	controller = Controller.new(pair, both_cards.cards, 145, [device])
	var visible_destination := device.position
	controller.start(pair[0])
	until_phase(pair, controller, "object_move")
	check(pair[0].target == pair[0].clamp_position(visible_destination + Vector2(-54, -38)) and pair[1].target == pair[1].clamp_position(visible_destination + Vector2(54, -38)), "Move to visible object uses its current position rather than home")
	controller.deadline = 0
	advance(pair, controller)
	check(controller.phase == "idle" and not pair[0].conversation_controlled and pair[0].target == null and pair[1].target == null, "Object movement timeout releases both rather than hanging")
	pair = make_pair()
	device.put_away()
	device.home_position = Vector2.ZERO
	var wall_cards := Deck.parse([{"steps": [{"type": "move", "actor": "both", "tag": "game_device"}, {"type": "say", "speaker": "kadoka", "text": "はしっこ"}]}])
	controller = Controller.new(pair, wall_cards.cards, 145, [device])
	controller.start(pair[0])
	check(until_phase(pair, controller, "talk") and pair[0].bounds.has_point(pair[0].position) and pair[1].bounds.has_point(pair[1].position) and is_equal_approx(absf(pair[0].position.x - pair[1].position.x), 145) and is_equal_approx(pair[0].position.y, pair[1].position.y), "Even a wall-clamped object move restores full horizontal speech spacing")
	controller.cancel()
	var scene := load("res://main.tscn") as PackedScene
	var game := scene.instantiate()
	get_root().add_child(game)
	game.set_process(false)
	var scene_device = game.objects.back()
	check(not scene_device.visible and not game.object_views.back().visible and scene_device.snapshot().tag == "game_device", "Scene/log share initially hidden runtime placement state")
	scene_device.put_away()
	game.ghosts[0].position = Vector2(340, 350)
	game.ghosts[1].position = Vector2(460, 350)
	game.conversations = Controller.new(game.ghosts, parsed.cards, 145, game.objects)
	game.conversations.start(game.ghosts[0])
	until_phase(game.ghosts, game.conversations, "talk")
	game.refresh_views()
	check(scene_device.visible and game.object_views.back().visible and game.object_views.back().position == scene_device.position and game.bubbles[1].visible, "Scene renders taken object and subsequent dialogue from the same models")
	var output: String = game.option("screenshot")
	if not output.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(output) == OK, "Object conversation screenshot saves")
	game.send_click(Vector2(800, 200))
	check(game.conversations.phase == "idle" and game.ghosts[0].target != null and scene_device.visible, "Click cancels tagged sequence and starts collection without undoing take")
	scene_device.put_away()
	game.refresh_views()
	check(not game.object_views.back().visible, "Put removes the sprite from screen")
	game.free()
	finish()


func finish() -> void:
	print("GODOT_OBJECT_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
