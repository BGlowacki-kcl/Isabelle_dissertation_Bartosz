// isabelle_bug_tests/ is at src/Tools/jEdit/src/isabelle_bug_tests/
// so Isabelle home = ../../../../..
val isabelleHome = {
  val envHome = sys.env.get("ISABELLE_HOME").map(file(_))
  envHome.getOrElse {
    // Walk up from project root: isabelle_bug_tests -> src -> jEdit -> Tools -> src -> Isabelle2025
    var d = file(".").getAbsoluteFile
    while (d != null && !((d / "lib" / "classes" / "isabelle.jar").exists())) d = d.getParentFile
    if (d != null) d else sys.error("Cannot find Isabelle home. Set ISABELLE_HOME.")
  }
}

name := "isabelle-bug-tests"
version := "0.1.0"
scalaVersion := "3.3.4"

// Use Isabelle's own Scala 3.3.4 compiler and library
dependencyOverrides += "org.scala-lang" %% "scala3-library" % "3.3.4"

// Real Isabelle classes — full runtime classpath mirroring lib/scripts/Isabelle_app
Compile / unmanagedJars ++= Seq(
  // Core Isabelle
  isabelleHome / "lib" / "classes" / "isabelle.jar",
  isabelleHome / "lib" / "classes" / "isabelle_graphbrowser.jar",
  // Isabelle setup (isabelle.setup.Environment et al)
  isabelleHome / "contrib" / "isabelle_setup-20240327" / "lib" / "isabelle_setup.jar",
  // jEdit
  isabelleHome / "contrib" / "jedit-20250215" / "jedit5.7.0-patched" / "jedit.jar",
  // XZ / ZSTD compression (used by Bash process temp-file handling)
  isabelleHome / "contrib" / "xz-java-1.10" / "lib" / "xz-1.10.jar",
  isabelleHome / "contrib" / "zstd-jni-1.5.6-8" / "zstd-jni-1.5.6-8.jar",
  // SQLite
  isabelleHome / "contrib" / "sqlite-3.48.0.0" / "lib" / "sqlite-jdbc-3.48.0.0.jar",
  isabelleHome / "contrib" / "sqlite-3.48.0.0" / "lib" / "slf4j-api-2.0.16.jar",
  isabelleHome / "contrib" / "sqlite-3.48.0.0" / "lib" / "slf4j-nop-2.0.16.jar",
  // Scala runtime extras
  isabelleHome / "contrib" / "scala-3.3.4" / "lib" / "scala-library-2.13.14.jar",
  isabelleHome / "contrib" / "scala-3.3.4" / "lib" / "scala3-library_3-3.3.4.jar",
  isabelleHome / "contrib" / "scala-3.3.4" / "lib" / "scala-parallel-collections_3-1.0.4.jar",
  isabelleHome / "contrib" / "scala-3.3.4" / "lib" / "scala-xml_3-2.3.0.jar",
  isabelleHome / "contrib" / "scala-3.3.4" / "lib" / "scala-swing_3-3.0.0.jar",
  // Misc
  isabelleHome / "contrib" / "flatlaf-3.5.4-1" / "lib" / "flatlaf-3.5.4-no-natives.jar",
  isabelleHome / "contrib" / "jsoup-1.18.3" / "lib" / "jsoup-1.18.3.jar",
  isabelleHome / "contrib" / "postgresql-42.7.5" / "lib" / "postgresql-42.7.5.jar",
)

// Fork so System.exit() doesn't kill sbt; also so thread pool is fresh
Compile / run / fork := true

// Use Isabelle's bundled JDK 21 (isabelle.jar is compiled for class file v65)
run / javaHome := {
  val jdk = isabelleHome / "contrib" / "jdk-21.0.6" / "x86_64-linux"
  if (jdk.exists()) Some(jdk) else None
}

run / javaOptions ++= Seq(
  "-Djava.awt.headless=false",
  s"-Disabelle.root=${isabelleHome.getAbsolutePath}"
)

// Pass ISABELLE_ROOT as an environment variable so isabelle.setup.Environment can find it
run / envVars := Map("ISABELLE_ROOT" -> isabelleHome.getAbsolutePath)
