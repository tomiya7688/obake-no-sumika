extends SceneTree

const ContentLoader = preload("res://scripts/content_loader.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
const Deck = preload("res://scripts/conversation_deck.gd")
const Controller = preload("res://scripts/conversation_controller.gd")
const BubbleView = preload("res://scripts/bubble_view.gd")
var checks: int = 0
var failures: Array[String] = []
var speech_steps := [
	{"type": "say", "speaker": "kadoka", "text": "みかん、たべる？"},
	{"type": "say", "speaker": "maru", "text": "食べるのだ！"},
	{"type": "say", "speaker": "kadoka", "text": "柿もあるよ"},
]
var definitions: Array


func _initialize() -> void:
	call_deferred("run_tests")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func make_pair() -> Array:
	return [
		GhostModel.new(definitions[0], Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345),
		GhostModel.new(definitions[1], Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345),
	]


func advance(pair: Array, controller: RefCounted, delta: float = 1.0 / 60) -> void:
	for ghost in pair:
		ghost.step(delta)
	controller.step(delta)


func run_tests() -> void:
	var loader := ContentLoader.new()
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var data := loader.load_project(root)
	check(not data.is_empty(), "Source content including conversation deck loads: " + loader.error)
	if data.is_empty():
		finish()
		return
	definitions = [data.characters[0].definition, data.characters[1].definition]
	var filtered := Deck.parse([
		{"weight": 2, "steps": speech_steps},
		{"steps": [speech_steps[0], {"type": "event", "event": "game_device"}]},
		{"steps": [speech_steps[0], {"type": "event", "event": "water_bath"}]},
	])
	check(filtered.error.is_empty() and filtered.cards.size() == 1 and filtered.skipped == 2, "Unsupported cards are excluded whole, not partially played")
	check(not data.conversations.is_empty() and data.skipped_conversations == 2, "Existing ordinary conversations are available; both event cards are excluded")
	var legacy := Deck.parse([{"kadoka": "  ここは\nおうち  ", "maru": "おうちなのだ！"}])
	check(legacy.error.is_empty() and legacy.cards[0].steps[0].text == "ここは おうち", "Legacy say data and whitespace are normalized without splitting characters")
	for bad in [
		{"weight": NAN, "steps": speech_steps},
		{"weight": true, "steps": speech_steps},
		{"weight": 0, "steps": speech_steps},
		{"steps": [{"type": "say", "speaker": "unknown", "text": "hello"}]},
		{"steps": [{"type": "typo", "text": "hello"}]},
	]:
		check(not Deck.parse([bad]).error.is_empty(), "Invalid card is rejected: " + str(bad))
	var pair := make_pair()
	var weighted := Controller.new(pair, [{"weight": 1, "steps": [speech_steps[0]]}, {"weight": 99, "steps": [speech_steps[1]]}], 145)
	var random := RandomNumberGenerator.new()
	random.seed = 99
	var heavy := 0
	for draw in 2000:
		if weighted.choose_card(random).steps[0].speaker == "maru":
			heavy += 1
	check(heavy > 1900 and heavy < 2000, "Selection respects relative weight without excluding the light card")
	pair = make_pair()
	var controller := Controller.new(pair, filtered.cards, 145)
	pair[0].position = Vector2(220, 300)
	pair[1].position = Vector2(620, 300)
	pair[1].action = "forward"
	pair[1].action_timer = 10
	pair[1].facing = 1
	pair[1].set_velocity(Vector2(20, 0))
	var receiver_before: Vector2 = pair[1].position
	var receiver_rng: int = pair[1].rng.state
	check(controller.start(pair[0]), "Initiator can approach")
	check(not pair[1].conversation_controlled and pair[1].action == "forward" and pair[1].rng.state == receiver_rng, "Request does not freeze or draw RNG from receiver")
	for frame in 30:
		advance(pair, controller)
	check(pair[1].position.x > receiver_before.x and not pair[1].conversation_controlled, "Receiver continues its random movement until approached")
	controller.cancel()
	check(not pair[0].conversation_controlled and not pair[1].conversation_controlled, "Cancel releases both models")
	pair = make_pair()
	controller = Controller.new(pair, filtered.cards, 145)
	pair[0].position = Vector2(340, 380)
	pair[1].position = Vector2(440, 380)
	pair[0].facing = 1
	pair[1].facing = 1
	pair[1].turning = false
	check(pair[1].begin_loop(), "Receiver can already be looping")
	controller.start(pair[0])
	advance(pair, controller)
	check(controller.phase == "wait_motion" and pair[1].action == "loop", "Approach waits for an existing loop without cancelling it")
	var no_early_speech := true
	var stable_pose := true
	var seen_lines: Array[String] = []
	for frame in 1800:
		advance(pair, controller)
		for ghost in pair:
			if not ghost.talk_text.is_empty():
				no_early_speech = no_early_speech and not ghost.turning and ghost.action != "loop"
				stable_pose = stable_pose and is_zero_approx(ghost.angle) and ghost.velocity == Vector2.ZERO and absf(pair[0].position.y - pair[1].position.y) < 0.01 and absf(pair[0].position.x - pair[1].position.x) >= 144.9
				var other = pair[1] if ghost == pair[0] else pair[0]
				stable_pose = stable_pose and (other.position.x - ghost.position.x) * ghost.facing > 0
				if seen_lines.is_empty() or seen_lines.back() != ghost.talk_text:
					seen_lines.append(ghost.talk_text)
		if controller.completed_count == 1:
			break
	check(no_early_speech and seen_lines.size() == 3, "Three editable lines play only after rotation completes")
	check(stable_pose, "Speaking models remain stopped, aligned and facing each other")
	check(seen_lines == ["みかん、たべる？", "食べるのだ！", "柿もあるよ"], "Speaker/text order matches the shared JSON")
	check(controller.phase == "idle" and not pair[0].conversation_controlled and pair[0].talk_cooldown > 0, "Completion clears speech and restores AI with cooldown")
	pair = make_pair()
	controller = Controller.new(pair, filtered.cards, 145)
	pair[0].position = Vector2(120, 130)
	pair[1].position = Vector2(130, 480)
	controller.start(pair[0])
	controller.align_pair()
	check(pair[0].target.x >= pair[0].bounds.position.x and pair[1].target.x <= pair[1].bounds.end.x and is_equal_approx(pair[0].target.y, pair[1].target.y) and is_equal_approx(absf(pair[1].target.x - pair[0].target.x), 145), "Wall meeting points keep full spacing and shared Y")
	controller.cancel()
	for action in GhostModel.ACTIONS:
		pair[0].weights[action] = 0
	pair[0].weights["seek_talk"] = 1
	pair[0].talk_cooldown = 0
	pair[1].talk_cooldown = 0
	pair[0].choose_action()
	check(pair[0].talk_request and pair[0].action == "seek_talk", "Configured seek_talk is a selectable AI action")
	controller.step(0)
	check(controller.phase == "seek", "AI request is consumed by the conversation controller")
	controller.cancel()
	pair[0].choose_action()
	check(not pair[0].talk_request and pair[0].action == "stop", "Cooldown prevents immediate repeated conversations")
	pair = make_pair()
	controller = Controller.new(pair, [], 145)
	check(not controller.start(pair[0]) and not pair[0].conversation_available, "No runnable deck suppresses conversation AI")
	var bubble := BubbleView.new()
	bubble.set_message("ぶつからないのだ、うわーーー。".repeat(4))
	check(bubble.lines.size() > 1 and bubble.extent.x <= 270.01, "Long Japanese line wraps within bubble width")
	bubble.free()
	var scene := load("res://main.tscn") as PackedScene
	var game := scene.instantiate()
	get_root().add_child(game)
	game.set_process(false)
	game.ghosts[0].position = Vector2(340, 350)
	game.ghosts[1].position = Vector2(460, 350)
	game.conversations.deck = filtered.cards
	game.conversations.start(game.ghosts[0])
	for frame in 600:
		advance(game.ghosts, game.conversations)
		if game.conversations.phase == "talk":
			break
	game.refresh_views()
	check(game.conversations.phase == "talk" and game.bubbles[0].visible, "Scene displays the actual speaking ghost's bubble")
	var output: String = game.option("screenshot")
	if not output.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(output) == OK, "Conversation screenshot saves")
	game.send_click(Vector2(800, 200))
	check(game.conversations.phase == "idle" and game.ghosts[0].target != null and game.ghosts[1].target != null and game.ghosts[0].talk_text.is_empty(), "Click cancels conversation and sends both to new targets")
	game.free()
	finish()


func finish() -> void:
	print("GODOT_CONVERSATION_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
