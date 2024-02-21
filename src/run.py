from utils.register import registry
import engine
import agents
import hospital
import utils
from utils.options import get_parser


if __name__ == '__main__':
    args = get_parser()
    scenario = registry.get_class(args.scenario)(args)
    if not args.parallel:
        scenario.run()
    else:
        scenario.parallel_run()
