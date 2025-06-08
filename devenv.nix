{ pkgs, lib, config, inputs, nixpkgs-unstable, devenv-zsh, devenv-awsenv, ... }:

let
  pkgs-unstable = import nixpkgs-unstable {
    system = pkgs.stdenv.system;
    config.allowUnfree = true;
  };

  script_python = (
    pkgs-unstable.python313.withPackages (python-pkgs: [
      python-pkgs.python-hcl2
      python-pkgs.graphviz
    ]
    )
  );
  scriptpyexe = "${script_python}/bin/python";
in
{
  imports = [ devenv-zsh.plugin devenv-awsenv.plugin ];

  awsenv.enable = true;

  languages.python = {
    libraries = with pkgs; [
      # numpy (pandas?), although it says it is a manylinux wheel, is not.
      # it depends on zlib, which isn't part of any manylinux spec.  Similar
      # reasons for ncurses5 and libxcrypt for usual data science stuff.
      ncurses5
      libxcrypt
      zlib
    ];
    enable = true;
    version = "3.11";
    venv = {
      enable = true;
      requirements = ''
        boto3
        kubernetes
        requests
      '';
    };
  };

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
    EDITOR="emacs -nw";
  };
  
  scripts.deploy.exec = ''
    exec "${scriptpyexe}" "$DEVENV_ROOT/deploy.py" "$@"
  '';

}
