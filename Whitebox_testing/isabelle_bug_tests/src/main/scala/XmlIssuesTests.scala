import isabelle.{XML, Markup}
import java.util.concurrent._
import java.util.concurrent.atomic._

object XmlIssuesTests {

  def buildDeepTree(depth: Int): XML.Tree = {
    var t: XML.Tree = XML.Text("leaf")
    for (_ <- 1 to depth) {
      t = XML.Elem(Markup("e", Nil), List(t))
    }
    t
  }

  def test_xml_null_string_output(): Boolean = {
    val result = XML.string_of_tree(XML.Text(null))
    result == "null"
  }

  def test_xml_filter_elements_overflow(): Boolean = {
    val deepTree = buildDeepTree(5000)
    try {
      XML.filter_elements(List(deepTree))
      false 
    } catch {
      case _: StackOverflowError => true 
      case _: Throwable => false
    }
  }

  def test_xml_cache_tree_overflow(): Boolean = {
    val deepTree = buildDeepTree(5000)
    val cache    = XML.Cache.make()
    try {
      cache.tree(deepTree)
      false
    } catch {
      case _: StackOverflowError => true
      case _: Throwable => false
    }
  }


  val tests: List[(String, () => Boolean)] = List(
    "xml_null_string_output"       -> (() => test_xml_null_string_output()),
    "xml_filter_elements_overflow" -> (() => test_xml_filter_elements_overflow()),
    "xml_cache_tree_overflow"      -> (() => test_xml_cache_tree_overflow()),
  )

  def main(args: Array[String]): Unit = {
    val pool    = Executors.newFixedThreadPool(tests.size)
    val futures = tests.map { case (name, f) =>
      name -> pool.submit(new Callable[Boolean] { def call() = f() })
    }
    pool.shutdown()
    pool.awaitTermination(120, TimeUnit.SECONDS)

    println("\n" + "=" * 60)
    println("  Isabelle PIDE Confirmed-Fixed Suite")
    println("=" * 60)
    var regressions = 0
    for ((name, fut) <- futures) {
      val regressed = try fut.get() catch {
        case e: Exception => println(s"  [ERROR] $name: $e"); false
      }
      val label = if (regressed) "REGRESSION DETECTED" else "PASS"
      println(s"  [$label] $name")
      if (regressed) regressions += 1
    }
    println("=" * 60)
    println(s"  $regressions / ${tests.size} regressions detected")
    println("=" * 60)
    System.exit(if (regressions > 0) 1 else 0)
  }
}
