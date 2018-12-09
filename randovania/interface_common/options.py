import dataclasses
import json
from pathlib import Path
from typing import Optional, TypeVar, Callable, Any

from randovania.game_description.resources import PickupEntry
from randovania.interface_common import persistence
from randovania.resolver.layout_configuration import LayoutConfiguration, LayoutRandomizedFlag, LayoutEnabledFlag, \
    LayoutTrickLevel
from randovania.resolver.patcher_configuration import PatcherConfiguration


def _convert_logic(layout_logic: str) -> str:
    if layout_logic == "no-glitches":
        return "no-tricks"
    return layout_logic


T = TypeVar("T")


def identity(v: T) -> T:
    return v


@dataclasses.dataclass(frozen=True)
class Serializer:
    encode: Callable[[Any], Any]
    decode: Callable[[Any], Any]


_SERIALIZER_FOR_FIELD = {
    "show_advanced_options": Serializer(identity, bool),
    "create_spoiler": Serializer(identity, bool),
    "output_directory": Serializer(str, Path),
    "patcher_configuration": Serializer(lambda p: p.as_json, PatcherConfiguration.from_json_dict),
    "layout_configuration": Serializer(lambda p: p.as_json, LayoutConfiguration.from_json_dict),
}


def _get_persisted_options_from_data(persisted_data: dict) -> dict:
    version = persisted_data.get("version", 0)
    if version < 1 or version > 2:
        return {}

    if version == 2:
        return persisted_data["options"]

    options = persisted_data["options"]
    results = {}

    try:
        results["patcher_configuration"] = {
            "disable_hud_popup": options["hud_memo_popup_removal"],
            "menu_mod": options["include_menu_mod"],
        }
    except KeyError as e:
        print("Unable to port patcher_configuration to new version, got {}".format(e))

    try:
        results["layout_configuration"] = {
            "trick_level": _convert_logic(options["layout_logic"]),
            "sky_temple_keys": options["sky_temple_keys"],
            "item_loss": options["item_loss"],
            "elevators": options["elevators"],
            "pickup_quantities": options["pickup_quantities"],
        }
    except KeyError as e:
        print("Unable to port layout_configuration to new version, got {}".format(e))

    return {}


def _return_with_default(value: Optional[T], default_factory: Callable[[], T]) -> T:
    """
    Returns the given value is if it's not None, otherwise call default_factory
    :param value:
    :param default_factory:
    :return:
    """
    if value is None:
        return default_factory()
    else:
        return value


class Options:
    _data_dir: Path
    _show_advanced_options: Optional[bool] = None
    _create_spoiler: Optional[bool] = None
    _output_directory: Optional[Path] = None
    _patcher_configuration: Optional[PatcherConfiguration] = None
    _layout_configuration: Optional[LayoutConfiguration] = None

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @classmethod
    def with_default_data_dir(cls) -> "Options":
        return cls(persistence.user_data_dir())

    def load_from_disk(self):
        try:
            with self._data_dir.joinpath("config.json").open() as options_file:
                persisted_data = json.load(options_file)
        except FileNotFoundError:
            return

        persisted_options = _get_persisted_options_from_data(persisted_data)
        for field_name, serializer in _SERIALIZER_FOR_FIELD.items():
            value = persisted_options.get(field_name, None)
            if value is not None:
                setattr(self, "_" + field_name, serializer.decode(value))

    def save_to_disk(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)

        data_to_persist = {}
        for field_name, serializer in _SERIALIZER_FOR_FIELD.items():
            value = getattr(self, "_" + field_name, None)
            if value is not None:
                data_to_persist[field_name] = serializer.encode(value)

        with self._data_dir.joinpath("config.json").open("w") as options_file:
            json.dump(
                {
                    "version": 2,
                    "options": data_to_persist
                },
                options_file,
                indent=4,
                separators=(',', ': ')
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_to_disk()

    # Files paths

    @property
    def backup_files_path(self) -> Path:
        return self._data_dir.joinpath("backup")

    @property
    def game_files_path(self) -> Path:
        return self._data_dir.joinpath("extracted_game")

    # Access to Direct fields

    @property
    def create_spoiler(self) -> bool:
        return _return_with_default(self._create_spoiler, lambda: True)

    @create_spoiler.setter
    def create_spoiler(self, value: bool):
        self._create_spoiler = value

    @property
    def output_directory(self) -> Optional[Path]:
        return self._output_directory

    @output_directory.setter
    def output_directory(self, value: Optional[Path]):
        self._output_directory = value

    @property
    def patcher_configuration(self) -> PatcherConfiguration:
        return _return_with_default(self._patcher_configuration, PatcherConfiguration.default)

    @property
    def layout_configuration(self) -> LayoutConfiguration:
        return _return_with_default(self._layout_configuration, LayoutConfiguration.default)

    # Access to fields inside PatcherConfiguration

    @property
    def hud_memo_popup_removal(self) -> bool:
        return self.patcher_configuration.disable_hud_popup

    @hud_memo_popup_removal.setter
    def hud_memo_popup_removal(self, value: bool):
        self._patcher_configuration = dataclasses.replace(self.patcher_configuration, disable_hud_popup=value)

    @property
    def include_menu_mod(self) -> bool:
        return self.patcher_configuration.menu_mod

    @include_menu_mod.setter
    def include_menu_mod(self, value: bool):
        self._patcher_configuration = dataclasses.replace(self.patcher_configuration, menu_mod=value)

    # Access to fields inside LayoutConfiguration

    @property
    def layout_configuration_trick_level(self) -> LayoutTrickLevel:
        return self.layout_configuration.trick_level

    @layout_configuration_trick_level.setter
    def layout_configuration_trick_level(self, value: LayoutTrickLevel):
        self._layout_configuration = dataclasses.replace(self.layout_configuration, trick_level=value)

    @property
    def layout_configuration_sky_temple_keys(self) -> LayoutRandomizedFlag:
        return self.layout_configuration.sky_temple_keys

    @layout_configuration_sky_temple_keys.setter
    def layout_configuration_sky_temple_keys(self, value: LayoutRandomizedFlag):
        self._layout_configuration = dataclasses.replace(self.layout_configuration, sky_temple_keys=value)

    @property
    def layout_configuration_elevators(self) -> LayoutRandomizedFlag:
        return self.layout_configuration.elevators

    @layout_configuration_elevators.setter
    def layout_configuration_elevators(self, value: LayoutRandomizedFlag):
        self._layout_configuration = dataclasses.replace(self.layout_configuration, elevators=value)

    @property
    def layout_configuration_item_loss(self) -> LayoutEnabledFlag:
        return self.layout_configuration.item_loss

    @layout_configuration_item_loss.setter
    def layout_configuration_item_loss(self, value: LayoutEnabledFlag):
        self._layout_configuration = dataclasses.replace(self.layout_configuration, item_loss=value)

    def quantity_for_pickup(self, pickup: PickupEntry) -> int:
        return self.layout_configuration.quantity_for_pickup(pickup)

    def set_quantity_for_pickup(self, pickup: PickupEntry, new_quantity: int) -> None:
        old_pickup_quantities = self.layout_configuration.pickup_quantities
        quantities = old_pickup_quantities.pickups_with_custom_quantities
        quantities[pickup] = new_quantity
        self._layout_configuration = dataclasses.replace(
            self.layout_configuration,
            pickup_quantities=old_pickup_quantities.with_new_quantities(quantities))
