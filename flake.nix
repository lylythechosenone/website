{
  description = "Build environment for lylythechosenone.is-a.dev";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";

  outputs = { self, nixpkgs }:
    let
      forAllSystems = f:
        nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ]
          (system: f nixpkgs.legacyPackages.${system});

      jekyllEnv = pkgs: pkgs.ruby.withPackages (ps: with ps; [ jekyll jekyll-avatar kramdown-parser-gfm ]);
    in
    {
      devShells = forAllSystems (pkgs: pkgs.mkShell {
        env.JEKYLL_NO_BUNDLER_REQUIRE = "1";
        env.RUBYOPT = "-Eutf-8";
        packages = [ (jekyllEnv pkgs) ];
      });

      packages = forAllSystems (pkgs: {
        website = pkgs.stdenvNoCC.mkDerivation {
          pname = "lylythechosenone-website";
          version = self.shortRev or self.dirtyShortRev or "dirty";
          src = self;
          nativeBuildInputs = [ (jekyllEnv pkgs) ];
          env.JEKYLL_NO_BUNDLER_REQUIRE = "1";
          env.RUBYOPT = "-Eutf-8";
          buildPhase = ''
            export JEKYLL_ENV=production
            jekyll build --destination $out
          '';
          dontInstall = true;
        };
        default = self.packages.${pkgs.system}.website;
      });
    };
}
