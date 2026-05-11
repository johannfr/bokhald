{
  description = "Bokhald - Personal finance/accounting software";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python312;
          pythonPkgs = python.pkgs;
          bokhald = pythonPkgs.buildPythonApplication {
            pname = "bokhald";
            version = "0.1.0";
            src = ./.;
            pyproject = true;
            build-system = [ pythonPkgs.setuptools ];
            dependencies = [
              pythonPkgs.nicegui
              pythonPkgs.sqlalchemy
              pythonPkgs.alembic
              pythonPkgs.babel
            ];
          };
        in
        {
          default = bokhald;
        }
      );

      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python312;
        in
        {
          default = pkgs.mkShell {
            packages = [
              (python.withPackages (ps: [
                ps.nicegui
                ps.sqlalchemy
                ps.alembic
                ps.babel
              ]))
            ];
            env.BOKHALD_DEV = "1";
          };
        }
      );
    };
}
