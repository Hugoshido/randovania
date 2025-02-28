import functools
import json
from dataclasses import dataclass
from random import Random
from typing import Iterator

from randovania.bitpacking import bitpacking
from randovania.bitpacking.bitpacking import BitPackValue, BitPackDecoder
from randovania.games import default_data
from randovania.games.game import RandovaniaGame
from randovania.interface_common.preset_manager import PresetManager
from randovania.layout.preset import Preset

_PERMALINK_MAX_SEED = 2 ** 31
_PERMALINK_PLAYER_COUNT_LIMITS = (2, 256)


def raw_database_hash(data: dict) -> int:
    return bitpacking.single_byte_hash(json.dumps(data, separators=(',', ':')).encode("UTF-8"))


def game_db_hash(game: RandovaniaGame) -> int:
    data = default_data.read_json_then_binary(game)[1]
    return raw_database_hash(data)


def _get_unique_games(presets: list[Preset]) -> Iterator[RandovaniaGame]:
    games = set()
    for preset in presets:
        if preset.game not in games:
            games.add(preset.game)
            yield preset.game


def encode_game_list(games: tuple[RandovaniaGame, ...]):
    yield from bitpacking.encode_tuple(games, functools.partial(RandovaniaGame.bit_pack_encode, metadata={}))


def decode_game_list(decoder: BitPackDecoder) -> tuple[RandovaniaGame, ...]:
    return bitpacking.decode_tuple(decoder, functools.partial(RandovaniaGame.bit_pack_unpack, metadata={}))


def try_decode_game_list(data: bytes) -> tuple[RandovaniaGame, ...] | None:
    try:
        return decode_game_list(BitPackDecoder(data))
    except (ValueError, IndexError):
        return None


@dataclass(frozen=True)
class GeneratorParameters(BitPackValue):
    seed_number: int
    spoiler: bool
    presets: list[Preset]
    development: bool = False

    def __post_init__(self):
        if self.seed_number is None:
            raise ValueError("Missing seed number")
        if not (0 <= self.seed_number < _PERMALINK_MAX_SEED):
            raise ValueError(f"Invalid seed number: {self.seed_number}")

        if not isinstance(self.presets, list):
            raise ValueError("presets must be a list")

        if not self.spoiler and self.development:
            raise ValueError("Race permalinks can't have development enabled")

        object.__setattr__(self, "__cached_as_bytes", None)

    def bit_pack_encode(self, metadata) -> Iterator[tuple[int, int]]:
        yield from encode_game_list(tuple(preset.game for preset in self.presets))
        yield self.seed_number, _PERMALINK_MAX_SEED
        yield from bitpacking.encode_bool(self.spoiler)
        if self.spoiler:
            yield from bitpacking.encode_bool(self.development)

        manager = PresetManager(None)
        for preset in self.presets:
            yield from preset.bit_pack_encode({"manager": manager})

        if not self.development:
            for game in _get_unique_games(self.presets):
                yield game_db_hash(game), 256

    @classmethod
    def bit_pack_unpack(cls, decoder: BitPackDecoder, metadata) -> "GeneratorParameters":
        games = decode_game_list(decoder)
        seed_number = decoder.decode_single(_PERMALINK_MAX_SEED)
        spoiler = bitpacking.decode_bool(decoder)
        development = False
        if spoiler:
            development = bitpacking.decode_bool(decoder)

        manager = PresetManager(None)
        presets = [
            Preset.bit_pack_unpack(decoder, {"manager": manager, "game": game})
            for game in games
        ]

        if not development:
            for game in _get_unique_games(presets):
                included_data_hash = decoder.decode_single(256)
                expected_data_hash = game_db_hash(game)
                if included_data_hash != expected_data_hash:
                    raise ValueError("Expected {} database with hash {}, but found {} instead.".format(
                        game.long_name, included_data_hash, expected_data_hash,
                    ))

        return GeneratorParameters(seed_number, spoiler, presets, development=development)

    @property
    def as_bytes(self) -> bytes:
        key = "__cached_as_bytes"
        result = object.__getattribute__(self, key)
        if result is None:
            result = bitpacking.pack_value(self)
            object.__setattr__(self, key, result)

        return result

    def create_rng(self):
        return Random(self.seed_number if self.development else self.as_bytes)

    @classmethod
    def from_bytes(cls, b: bytes) -> "GeneratorParameters":
        decoder = BitPackDecoder(b)
        result = GeneratorParameters.bit_pack_unpack(decoder, {})
        decoder.ensure_data_end()
        return result

    @property
    def player_count(self) -> int:
        return len(self.presets)

    def get_preset(self, index: int) -> Preset:
        return self.presets[index]
