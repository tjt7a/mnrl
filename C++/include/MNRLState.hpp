// Kevin Angstadt
// angstadt {at} virginia.edu
//
// MNRLState Object

#ifndef MNRLSTATE_HPP
#define MNRLSTATE_HPP

#include <string>
#include <utility>
#include <vector>
#include <map>
#include <json11.hpp>

#include "MNRLDefs.hpp"
#include "MNRLNode.hpp"
#include "MNRLPort.hpp"

namespace MNRL {
	class MNRLDefs;
	class MNRLNode;
	class MNRLPort;
	class MNRLState : public MNRLNode {
		public:
			MNRLState(
				std::vector<std::pair<std::string,std::string>> outputSymbols,
				MNRLDefs::EnableType enable,
				std::string id,
				bool report,
				bool latched,
				int reportId,
				std::shared_ptr<json11::Json::object> attributes
			);
			virtual ~MNRLState();

			virtual json11::Json to_json();

		protected:
			std::vector<std::pair<std::string,std::string>> outputSymbols;
			bool latched;
			int reportId;

		private:
			static port_def gen_input() {
				port_def in;
				in.push_back(
					std::shared_ptr<MNRLPort>( new MNRLPort(
							MNRLDefs::STATE_INPUT,
							1
						)
					)
				);
			}
			static port_def gen_output(std::vector<std::pair<std::string,std::string>> &outputSymbols) {
				port_def outs;
				for(auto &o_s : outputSymbols) {
					outs.push_back(
						std::shared_ptr<MNRLPort>(new MNRLPort(o_s.first, 1))
					);
				}
				return outs;
			}
	};
}

#endif