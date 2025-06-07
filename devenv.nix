{ pkgs, lib, config, inputs, nixpkgs-2411, nixpkgs-unstable, devenv-zsh, ... }:

let
  pkgs-2411 = import nixpkgs-2411 {
    system = pkgs.stdenv.system;
    config.allowUnfree = true;
  };

  pkgs-unstable = import nixpkgs-unstable {
    system = pkgs.stdenv.system;
    config.allowUnfree = true;
  };

  script_python = (
    # Use pkgs-2411 and 3.11 to download cached dependences instead of
    # building
    pkgs-2411.python311.withPackages (python-pkgs: [
      python-pkgs.boto3
      python-pkgs.kubernetes
      python-pkgs.jupytext
      python-pkgs.requests
      python-pkgs.pyjwt
      python-pkgs.cryptography
      python-pkgs.python-hcl2
      python-pkgs.graphviz
    ]
    )
  );
  scriptpyexe = "${script_python}/bin/python";
in
{
  imports = [ devenv-zsh.plugin ];

  packages = [
    pkgs-unstable.jq
    pkgs-unstable.awscli2
    pkgs-unstable.ssm-session-manager-plugin # for aws
    pkgs-unstable.terraform
    pkgs-unstable.kubectl
    pkgs-unstable.fluxcd
    pkgs-unstable.terramate
    pkgs-unstable.age
    pkgs-unstable.expect
    pkgs-unstable.tfsec
    pkgs-unstable.eksctl
    pkgs-unstable.k9s
    pkgs-unstable.velero
    pkgs-unstable.playwright-test
    pkgs-unstable.trivy
    pkgs-unstable.bashInteractive # fix launching bash noninteractively
    pkgs-unstable.git
  ];

  env = {
    CHECKPOINT_DISABLE = "1"; # disable terraform spyware
    DISABLE_CHECKPOINT = "1"; # disable terramate spyware
  };
  
  scripts.deploy.exec = ''
    exec "${scriptpyexe}" "$DEVENV_ROOT/deploy.py" "$@"
  '';

}
