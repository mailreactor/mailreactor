{
  description = "Mail Reactor - Headless Email Client";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python310
            uv
          ];

          shellHook = ''
            echo
            echo "Mail Reactor Development Environment"
            echo "$(python --version) | $(uv --version)"
            echo
            
            # Only show quick start if no virtual env exists (first time)
            if [ ! -d .venv ]; then
              echo "Quick start:"
              echo "  uv venv --python $(which python)"
              echo "  source .venv/bin/activate" 
              echo "  uv pip install -e \".[dev]\""
              echo
            fi
          '';
        };
      }
    );
}
