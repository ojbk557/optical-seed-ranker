from pathlib import Path

from optical_seed_ranker.ingest import parse_lenslibrary_properties


def test_parse_lenslibrary_image_space_rows(tmp_path: Path):
    source = tmp_path / "lens_properties_list.txt"
    source.write_text(
        """                                                                    image_space
filename               lens_type                focal_length(mm)        f-number        FFOV(deg)        N_surfaces        N_elements        ref
1975678                camera                   92.6                    1.5             42.0             10                7                 Bertele1934
Shafer1980             x-ray telescope          125                     N/A             1.0              2                 2                 Shafer1980
-------------------------------------------------------------------------------------------------------------------------------------
                                                                     object_space
7301707-spherical      lithography_lens         0.68                    106.0           26.5            62                31                Shafer2007
""",
        encoding="utf-8",
    )
    result = parse_lenslibrary_properties(source)
    assert len(result.seeds) == 1
    assert result.seeds[0].seed_id == "1975678"
    assert result.seeds[0].f_number == 1.5
    assert result.skipped_lines == 2
