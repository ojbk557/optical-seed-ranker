import asyncio
import warnings

import pytest
from pydantic_settings import IncompleteFieldDefinitionWarning

import optical_seed_ranker.mcp_server as mcp_server
from optical_seed_ranker.index_io import write_seed_index
from optical_seed_ranker.mcp_server import create_server
from optical_seed_ranker.models import SeedRecord


def test_mcp_server_rejects_non_loopback_binding():
    with pytest.raises(ValueError, match="loopback"):
        create_server(host="0.0.0.0")


def test_mcp_server_registers_and_calls_local_tools(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", IncompleteFieldDefinitionWarning)
        server = create_server(index_path=tmp_path / "missing.csv")
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {
        "seedranker_derive_uv_target",
        "seedranker_search_uv_structures",
        "seedranker_get_local_structure",
        "seedranker_local_status",
    }

    async def call_status_and_search():
        _, status = await server._tool_manager.call_tool(
            "seedranker_local_status", {}, convert_result=True
        )
        _, search = await server._tool_manager.call_tool(
            "seedranker_search_uv_structures",
            {
                "field_x_full_deg": 60,
                "field_y_full_deg": 60,
                "detector_diameter_mm": 18,
                "entrance_pupil_min_mm": 12,
                "wavelength_min_nm": 240,
                "wavelength_max_nm": 320,
                "top_k": 1,
            },
            convert_result=True,
        )
        return status, search

    status, search = asyncio.run(call_status_and_search())
    assert status["loopback_only"] is True
    assert status["curated_patent_seed_count"] == 6
    assert search["candidates"][0]["evidence"]["known_gaps"]


def test_mcp_cli_treats_keyboard_interrupt_as_a_clean_shutdown(
    monkeypatch, capsys
):
    class InterruptedServer:
        def run(self, *, transport):
            assert transport == "streamable-http"
            raise KeyboardInterrupt

    monkeypatch.setattr(mcp_server, "create_server", lambda **kwargs: InterruptedServer())

    assert mcp_server.main(["--port", "8891"]) == 0
    assert "Server stopped." in capsys.readouterr().out


def test_mcp_structure_routes_qualified_handles_when_providers_collide(tmp_path):
    prescription = tmp_path / "collision.ZMX"
    prescription.write_text(
        "UNIT MM X W X CM MR CPMM\n"
        "SURF 0\n TYPE STANDARD\n CURV 0\n DISZ INFINITY\n"
        "SURF 1\n TYPE STANDARD\n CURV 0\n DISZ 0\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "seeds.csv"
    write_seed_index(
        [
            SeedRecord(
                seed_id="CN113504627B",
                lens_type="camera",
                focal_length_mm=20,
                f_number=2,
                full_fov_deg=40,
                surface_count=2,
                element_count=1,
                reference="local-collision",
                source="curated_patent",
                source_path=str(prescription),
            )
        ],
        index_path,
    )
    server = create_server(index_path=index_path)

    async def call_structures():
        with pytest.raises(Exception, match="ambiguous"):
            await server._tool_manager.call_tool(
                "seedranker_get_local_structure",
                {"seed_id": "CN113504627B"},
                convert_result=True,
            )
        _, local = await server._tool_manager.call_tool(
            "seedranker_get_local_structure",
            {"seed_id": "local:CN113504627B"},
            convert_result=True,
        )
        _, patent = await server._tool_manager.call_tool(
            "seedranker_get_local_structure",
            {"seed_id": "patent:CN113504627B"},
            convert_result=True,
        )
        return local, patent

    local, patent = asyncio.run(call_structures())
    assert local["seed"]["seed_handle"] == "local:CN113504627B"
    assert local["prescription"]["surface_count_including_object_and_image"] == 2
    assert patent["seed"]["seed_handle"] == "patent:CN113504627B"
    assert len(patent["prescription"]["surfaces"]) == 19


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_mcp_rejects_non_finite_json_numeric_inputs(value, tmp_path):
    server = create_server(index_path=tmp_path / "missing.csv")

    async def call_invalid_target():
        with pytest.raises(Exception, match="finite"):
            await server._tool_manager.call_tool(
                "seedranker_derive_uv_target",
                {
                    "field_x_full_deg": 60,
                    "field_y_full_deg": 60,
                    "detector_diameter_mm": value,
                    "entrance_pupil_min_mm": 12,
                },
                convert_result=True,
            )

    asyncio.run(call_invalid_target())
