from tools.aws.scope_shared.core.phases import deploy_phases, teardown_phases


def test_deploy_phases_kube_includes_eks():
    phases = deploy_phases("kube")
    assert "Apply EKS stack" in phases


def test_teardown_phases_all_order():
    phases = teardown_phases("all")
    assert phases[0] == "Destroy nonkube stack"
