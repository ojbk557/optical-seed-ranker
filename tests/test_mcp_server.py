import asyncio

import pytest

from optical_seed_ranker.mcp_server import create_server


def test_mcp_server_rejects_non_loopback_binding():
    with pytest.raises(ValueError, match="loopback"):
        create_server(host="0.0.0.0")


def test_mcp_server_registers_and_calls_local_tools(tmp_path):
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
