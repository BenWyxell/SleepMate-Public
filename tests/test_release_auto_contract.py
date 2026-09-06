from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_auto_syncs_main_only_after_verified_artifacts() -> None:
    workflow = (ROOT / ".github/workflows/release-auto.yml").read_text(encoding="utf-8")

    assert 'base_main_sha=$BASE_MAIN_SHA' in workflow
    assert 'git merge-base --is-ancestor "$BASE_MAIN_SHA" "$RELEASE_AUTO_SHA"' in workflow
    assert "Synchronize canonical main to verified release source" in workflow
    assert "CURRENT_MAIN=\"$(gh api \"repos/$GITHUB_REPOSITORY/git/ref/heads/main\" --jq '.object.sha')\"" in workflow
    assert "CURRENT_RELEASE_AUTO=\"$(gh api \"repos/$GITHUB_REPOSITORY/git/ref/heads/release-auto\" --jq '.object.sha')\"" in workflow
    assert '[[ "$CURRENT_MAIN" == "$BASE_MAIN_SHA" ]]' in workflow
    assert '[[ "$CURRENT_RELEASE_AUTO" == "$RELEASE_SHA" ]]' in workflow
    assert 'git merge-base --is-ancestor "$CURRENT_MAIN" "$RELEASE_SHA"' in workflow
    assert '"repos/$GITHUB_REPOSITORY/git/refs/heads/main"' in workflow
    assert '-F force=false' in workflow

    verify_pos = workflow.index("Re-verify exact canonical artifacts")
    sync_pos = workflow.index("Synchronize canonical main to verified release source")
    publish_pos = workflow.index("Publish verified GitHub Release automatically")
    assert verify_pos < sync_pos < publish_pos
